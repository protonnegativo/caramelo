import asyncio

import httpx
import pytest
import respx

from caramelo.cli import main
from caramelo.engine import check, profile_exists
from caramelo.sites import Site, list_info
from caramelo.sources import (convert_all, dedupe, from_maigret, from_sherlock, from_whatsmyname, merge,
                              site_domain)

WMN = {"sites": [
    {"name": "GitHub (User)", "uri_check": "https://api.github.com/users/{account}", "uri_pretty": "https://github.com/{account}",
     "e_code": 200, "e_string": '"login":', "m_code": 404, "m_string": "Not Found", "known": ["blue"], "cat": "coding"},
    {"name": "Dating Site", "uri_check": "https://date.example/{account}", "e_code": 200, "e_string": "x",
     "m_code": 404, "m_string": "y", "known": ["a"], "cat": "dating"},
]}
SHERLOCK = {
    "$schema": "x",
    "GitHub": {"errorType": "status_code", "url": "https://www.github.com/{}", "urlMain": "https://www.github.com/",
               "username_claimed": "blue"},
    "Codepen": {"errorType": "message", "errorMsg": ["Page not found"], "url": "https://codepen.io/{}",
                "urlMain": "https://codepen.io/", "username_claimed": "blue", "regexCheck": "^[a-z]{3,}$"},
    "Adult": {"errorType": "status_code", "url": "https://adult.example/{}", "urlMain": "x", "username_claimed": "a",
              "isNSFW": True},
}
MAIGRET = {
    "engines": {"XenForo": {"name": "XenForo", "site": {
        "checkType": "message", "absenceStrs": ["The specified member cannot be found"],
        "url": "{urlMain}{urlSubpath}/members/?username={username}"}}},
    "sites": {
        "Codepen": {"checkType": "status_code", "url": "https://codepen.io/{username}", "usernameClaimed": "x",
                    "usernameUnclaimed": "y", "tags": ["coding"]},
        "SomeForum": {"engine": "XenForo", "urlMain": "https://forum.example", "urlSubpath": "/community",
                      "usernameClaimed": "admin", "usernameUnclaimed": "noonewouldeverusethis7", "tags": ["forum", "de"]},
        "Old": {"checkType": "status_code", "url": "https://old.example/{username}", "disabled": True, "tags": []},
        "Cams": {"checkType": "status_code", "url": "https://cams.example/{username}", "tags": ["webcam"]},
        "ById": {"checkType": "status_code", "url": "https://id.example/{username}", "type": "steam_id", "tags": []},
    },
}


def run(coro):
    return asyncio.run(coro)


def test_each_source_is_converted_to_one_rule_format():
    wmn, sh, mg = from_whatsmyname(WMN), from_sherlock(SHERLOCK), from_maigret(MAIGRET)
    assert wmn[0]["mode"] == "string" and wmn[0]["profile_url"] == "https://github.com/{account}"
    codepen = next(r for r in sh if r["name"] == "Codepen")
    assert codepen["mode"] == "message" and codepen["absence"] == ["Page not found"]
    assert codepen["profile_url"] == "https://codepen.io/{account}"
    forum = next(r for r in mg if r["name"] == "SomeForum")
    assert forum["check_url"] == "https://forum.example/community/members/?username={account}"
    assert forum["category"] == "forum" and forum["absence"] == ["The specified member cannot be found"]


def test_unwanted_sites_are_filtered_out():
    assert "Adult" not in {r["name"] for r in from_sherlock(SHERLOCK)}
    names = {r["name"] for r in from_maigret(MAIGRET)}
    assert not names & {"Old", "Cams", "ById"}  # disabled, adult tag, non-username identifier


def test_merge_removes_duplicates_by_domain_with_source_priority():
    rules = merge({"whatsmyname": WMN, "sherlock": SHERLOCK, "maigret": MAIGRET})
    by_domain = {}
    for r in rules:
        by_domain.setdefault(site_domain(r["profile_url"]), []).append(r["source"])
    assert by_domain["github.com"] == ["whatsmyname"]
    assert by_domain["codepen.io"] == ["sherlock"]
    assert by_domain["forum.example"] == ["maigret"]
    assert "date.example" not in by_domain


def test_dedupe_after_validation_falls_back_to_the_next_source():
    rules = convert_all({"whatsmyname": WMN, "sherlock": SHERLOCK})
    # Pretend WhatsMyName's GitHub rule failed validation: Sherlock's GitHub rule must take its place.
    passed = [r for r in rules if not (r["source"] == "whatsmyname" and r["name"] == "GitHub (User)")]
    github = [r for r in dedupe(passed) if site_domain(r["profile_url"]) == "github.com"]
    assert [(r["source"], r["name"]) for r in github] == [("sherlock", "GitHub")]


def test_site_domain():
    assert site_domain("https://api.github.com/users/{account}") == "github.com"
    assert site_domain("https://www.bbc.co.uk/{account}") == "bbc.co.uk"


def _site(**kw):
    base = dict(name="S", source="sherlock", category="misc", mode="status",
                check_url="https://s.example/{account}", profile_url="https://s.example/{account}")
    return Site(**{**base, **kw})


@pytest.mark.parametrize("site,status,text,expected", [
    (_site(mode="status"), 200, "", True),
    (_site(mode="status"), 404, "", False),
    (_site(mode="status", error_codes=(200,)), 200, "", False),
    (_site(mode="message", absence=("not found",)), 200, "user not found", False),
    (_site(mode="message", absence=("not found",)), 200, "hello", True),
    (_site(mode="message", absence=("not found",)), 404, "hello", False),
    (_site(mode="message", presence=("profile-card",)), 200, "<div class=profile-card>", True),
    (_site(mode="message", presence=("profile-card",)), 200, "nothing", False),
    (_site(mode="redirect"), 302, "", False),
    (_site(mode="status", error_strings=("captcha",)), 200, "solve the captcha", None),
    (_site(mode="status"), 429, "", None),
])
def test_detection_modes(site, status, text, expected):
    assert profile_exists(site, status, text) == expected


@respx.mock
def test_redirect_mode_does_not_follow_redirects():
    respx.get("https://s.example/jane").respond(302, headers={"Location": "https://s.example/"})
    respx.get("https://s.example/").respond(200, text="home")

    async def go():
        async with httpx.AsyncClient() as c:
            return await check(c, _site(mode="redirect"), "jane", 5)
    assert run(go()) == (None, True)


def test_username_rules_skip_sites_that_cannot_have_it():
    async def go():
        async with httpx.AsyncClient() as c:
            return await check(c, _site(regex="^[a-z]{5,}$"), "ab", 5)
    assert run(go()) == (None, True)  # no request is made


def test_bundled_list_has_all_three_sources():
    info = list_info()
    assert info["sites"] > 1000
    assert set(info["by_source"]) == {"whatsmyname", "sherlock", "maigret"}


@respx.mock
def test_silent_prints_only_site_and_url(capsys):
    respx.get("https://api.github.com/users/jane").respond(200, json={"login": "jane", "id": 7, "name": "Jane"})
    assert main(["jane", "-s", "GitHub (User)", "--no-pivot", "--silent"]) == 0
    out, err = capsys.readouterr()
    assert out == "GitHub (User)\thttps://github.com/jane\n"
    assert err == ""

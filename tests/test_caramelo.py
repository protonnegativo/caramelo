import asyncio
import json

import httpx
import pytest
import respx

from caramelo import Dossier, Profile, investigate, username_variants
from caramelo.engine import _pivots, check, investigate_async
from caramelo.extractors import extract, from_page
from caramelo.sites import BLOCKED_CATEGORIES, Site, load_sites

SITE = Site(
    name="Example", source="whatsmyname", category="social", mode="string",
    check_url="https://ex.com/u/{account}", profile_url="https://ex.com/u/{account}",
    exists_code=200, exists_string="profile-ok",
)


def run(coro):
    return asyncio.run(coro)


async def _check(username):
    async with httpx.AsyncClient() as c:
        return await check(c, SITE, username, 5)


@respx.mock
def test_profile_is_confirmed_by_page_content():
    respx.get("https://ex.com/u/jane").respond(200, text='<meta property="og:title" content="Jane Doe"> profile-ok')
    profile, answered = run(_check("jane"))
    assert answered and profile.url == "https://ex.com/u/jane"
    assert profile.name == "Jane Doe"


@respx.mock
def test_200_page_without_the_marker_is_not_a_profile():
    respx.get("https://ex.com/u/nobody").respond(200, text="generic page")
    profile, answered = run(_check("nobody"))
    assert profile is None and answered


@respx.mock
def test_network_error_counts_as_no_response():
    respx.get("https://ex.com/u/x").mock(side_effect=httpx.ConnectTimeout("slow"))
    assert run(_check("x")) == (None, False)


def test_sensitive_categories_are_excluded():
    sites = load_sites()
    assert len(sites) > 500
    assert not {s.category for s in sites} & BLOCKED_CATEGORIES


def test_github_extractor_and_linked_accounts():
    body = json.dumps({"name": "Jane", "bio": "dev at https://jane.dev", "location": "Lisbon",
                       "created_at": "2020-05-04T10:00:00Z", "followers": 11, "blog": "jane.dev",
                       "twitter_username": "jane_tw"})
    d, source = extract("GitHub (User)", body, "jane")
    assert source == "api-github"
    assert d["name"] == "Jane" and d["location"] == "Lisbon" and d["created_at"] == "2020-05-04"
    assert d["linked_accounts"]["twitter"] == "jane_tw"
    assert "https://jane.dev" in d["links"]


def test_keybase_extractor_reads_proofs():
    body = json.dumps({"them": [{"profile": {"full_name": "Jane"}, "proofs_summary": {"all": [
        {"proof_type": "github", "nametag": "janegh", "service_url": "https://github.com/janegh"}]}}]})
    d, _ = extract("Keybase", body, "jane")
    assert d["linked_accounts"]["github"] == "janegh"


def test_broken_extractor_does_not_raise():
    assert extract("GitHub (User)", "this is not json", "x")[0].get("name") is None


@pytest.mark.parametrize("title,site,expected", [
    ("Jane (@jane) • Instagram", "Instagram", "Jane (@jane)"),
    ("Steam Community :: proton", "Steam", "proton"),
    ("ProtonNegativo's profile on GOG.com", "GOG", "ProtonNegativo"),
    ("Wikidot.com: Jane", "Wikidot", "Jane"),
    ("Instagram", "Instagram", None),
])
def test_name_from_page_title(title, site, expected):
    page = f'<meta property="og:title" content="{title}">'
    assert from_page(page, site).get("name") == expected


def test_boilerplate_description_is_dropped():
    page = '<meta property="og:description" content="Follow jane on TradingView for chart analysis">'
    assert from_page(page, "TradingView").get("bio") is None


def test_username_variants_from_name():
    v = username_variants("João da Silva")
    assert v[:3] == ["joaosilva", "joao.silva", "joao_silva"]
    assert "jsilva" in v and all(" " not in x for x in v)


def test_pivots_skip_usernames_already_tried():
    d = Dossier(target="a", usernames_tried=["jane"])
    d.profiles = [Profile(site="GitHub (User)", url="u", username="jane",
                          linked_accounts={"twitter": "other", "keybase": "Jane"})]
    assert _pivots(d, 5) == {"other": "GitHub (User)"}


@respx.mock
def test_full_investigation_with_pivot():
    respx.get("https://api.github.com/users/jane").respond(200, json={
        "login": "jane", "id": 1, "name": "Jane", "twitter_username": "jane_x"})
    respx.get("https://api.github.com/users/jane_x").respond(404, json={"message": "Not Found"})
    d = run(investigate_async("jane", sites={"GitHub (User)"}))
    assert [p.username for p in d.profiles] == ["jane"]
    assert d.usernames_tried == ["jane", "jane_x"]
    assert json.loads(d.to_json())["summary"]["linked_accounts"] == {"twitter": ["jane_x"]}


def test_investigate_inside_running_loop_explains_what_to_do():
    async def inside():
        investigate("x")
    with pytest.raises(RuntimeError, match="investigate_async"):
        run(inside())


@pytest.mark.network
def test_real_github_lookup():
    d = investigate("torvalds", sites={"GitHub (User)"}, pivot=False)
    assert d.profiles and d.profiles[0].name == "Linus Torvalds"

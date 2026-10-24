"""Site lists from three open projects, converted to one rule format and merged without duplicates.

- WhatsMyName  https://github.com/WebBreacher/WhatsMyName  (CC BY-SA 4.0)
- Sherlock     https://github.com/sherlock-project/sherlock (MIT)
- Maigret      https://github.com/soxoj/maigret             (MIT)

Every rule says how to ask a site about a username and how to read the answer (`mode`):

- "string"   the profile exists when the status is `exists_code` and `exists_string` is in the page (WhatsMyName)
- "status"   the profile exists on a 2xx answer
- "message"  the profile exists when no `absence` text is in the page (and one `presence` text is, if given)
- "redirect" the profile exists on a 2xx answer without following redirects
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

URLS = {
    "whatsmyname": "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json",
    "sherlock": "https://raw.githubusercontent.com/sherlock-project/sherlock/master/sherlock_project/resources/data.json",
    "maigret": "https://raw.githubusercontent.com/soxoj/maigret/main/maigret/resources/data.json",
}
#: When two sources cover the same site, the rule from the earlier one wins.
PRIORITY = ("whatsmyname", "sherlock", "maigret")

#: Never checked: looking someone up on dating or adult sites serves to expose people far more than any
#: legitimate investigation. Tor/I2P sites can't be reached without those networks.
BLOCKED_CATEGORIES = frozenset({"dating", "xx NSFW xx", "adult"})
_BLOCKED_TAGS = frozenset({"dating", "erotic", "porn", "webcam", "tor", "i2p"})

#: Maigret tags → Caramelo category (first match wins; country-code tags are ignored).
_TAG_CATEGORY = [
    ("coding", "coding"), ("hacking", "tech"), ("tech", "tech"), ("gaming", "gaming"), ("social", "social"),
    ("mastodon", "social"), ("lemmy", "social"), ("messaging", "social"), ("music", "music"), ("video", "video"),
    ("streaming", "video"), ("movies", "video"), ("photo", "images"), ("art", "art"), ("design", "art"),
    ("crypto", "finance"), ("finance", "finance"), ("trading", "finance"), ("stock", "finance"),
    ("fintech", "finance"), ("shopping", "shopping"), ("classified", "shopping"), ("business", "business"),
    ("professional", "business"), ("career", "business"), ("freelance", "business"), ("news", "news"),
    ("blog", "blog"), ("writing", "blog"), ("forum", "forum"), ("discussion", "forum"), ("q&a", "forum"),
    ("wiki", "wiki"), ("hobby", "hobby"), ("sport", "hobby"), ("auto", "hobby"), ("travel", "hobby"),
    ("books", "hobby"), ("education", "education"), ("science", "education"), ("research", "education"),
]


def _rule(**fields) -> dict:
    base = {
        "name": "", "source": "", "category": "misc", "mode": "status", "check_url": "", "profile_url": "",
        "method": "GET", "body": None, "headers": {}, "exists_code": 200, "exists_string": "",
        "presence": [], "absence": [], "error_codes": [], "error_strings": [], "regex": None,
        "strip_chars": "", "known": [], "unclaimed": None,
    }
    base.update({k: v for k, v in fields.items() if v is not None})
    return base


def _as_list(value) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def from_whatsmyname(data: dict) -> list[dict]:
    rules = []
    for s in data["sites"]:
        if s.get("valid") is False:
            continue
        rules.append(_rule(
            name=s["name"], source="whatsmyname", category=s.get("cat") or "misc", mode="string",
            check_url=s["uri_check"], profile_url=s.get("uri_pretty") or s["uri_check"],
            method="POST" if s.get("post_body") else "GET", body=s.get("post_body"), headers=s.get("headers") or {},
            exists_code=int(s["e_code"]), exists_string=s["e_string"],
            absence=_as_list(s.get("m_string")) if s.get("m_code") == s.get("e_code") else [],
            strip_chars=s.get("strip_bad_char", ""), known=_as_list(s.get("known")),
        ))
    return rules


def _sherlock_url(url: str) -> str:
    return url.replace("{}", "{account}")


def from_sherlock(data: dict) -> list[dict]:
    rules = []
    for name, s in data.items():
        if name.startswith("$") or not isinstance(s, dict) or s.get("isNSFW"):
            continue
        kind = s.get("errorType")
        if isinstance(kind, list):  # a few sites combine checks; the message check is the strictest
            kind = "message" if "message" in kind else kind[0]
        mode = {"status_code": "status", "message": "message", "response_url": "redirect"}.get(kind)
        if not mode:
            continue
        payload = s.get("request_payload")
        rules.append(_rule(
            name=name, source="sherlock", mode=mode,
            check_url=_sherlock_url(s.get("urlProbe") or s["url"]), profile_url=_sherlock_url(s["url"]),
            method=(s.get("request_method") or ("POST" if payload else "GET")).upper(),
            body=_sherlock_url(json.dumps(payload)) if payload else None,
            headers={**({"Content-Type": "application/json"} if payload else {}), **(s.get("headers") or {})},
            absence=_as_list(s.get("errorMsg")) if mode == "message" else [],
            error_codes=[int(c) for c in _as_list(s.get("errorCode"))],
            regex=s.get("regexCheck"), known=_as_list(s.get("username_claimed")),
        ))
    return rules


def _maigret_url(template: str, site: dict) -> str:
    url = template.replace("{urlMain}", (site.get("urlMain") or "").rstrip("/"))
    url = url.replace("{urlSubpath}", site.get("urlSubpath") or "")
    return url.replace("{username}", "{account}")


def _maigret_category(tags: list[str]) -> str:
    for tag, category in _TAG_CATEGORY:
        if tag in tags:
            return category
    return "misc"


def from_maigret(data: dict) -> list[dict]:
    engines = data.get("engines", {})
    rules = []
    for name, own in data["sites"].items():
        s = {**engines.get(own.get("engine"), {}).get("site", {}), **own}
        tags = s.get("tags") or []
        if s.get("disabled") or s.get("type") not in (None, "username") or _BLOCKED_TAGS & set(tags):
            continue
        mode = {"status_code": "status", "message": "message", "response_url": "redirect"}.get(s.get("checkType"))
        if not mode or not s.get("url"):
            continue
        payload = s.get("requestPayload")
        method = "HEAD" if s.get("requestHeadOnly") else (s.get("requestMethod") or ("POST" if payload else "GET")).upper()
        rules.append(_rule(
            name=name, source="maigret", category=_maigret_category(tags), mode=mode,
            check_url=_maigret_url(s.get("urlProbe") or s["url"], s), profile_url=_maigret_url(s["url"], s),
            method=method, body=_maigret_url(json.dumps(payload), s) if payload else None,
            headers={**({"Content-Type": "application/json"} if payload else {}), **(s.get("headers") or {})},
            presence=_as_list(s.get("presenseStrs")) if mode == "message" else [],
            absence=_as_list(s.get("absenceStrs")) if mode == "message" else [],
            error_strings=list((s.get("errors") or {}).keys()),
            regex=s.get("regexCheck"), known=_as_list(s.get("usernameClaimed")), unclaimed=s.get("usernameUnclaimed"),
        ))
    return rules


CONVERTERS = {"whatsmyname": from_whatsmyname, "sherlock": from_sherlock, "maigret": from_maigret}


def site_domain(url: str) -> str:
    """Registrable domain of a URL: api.github.com → github.com, www.bbc.co.uk → bbc.co.uk."""
    host = (urlsplit(url.replace("{account}", "x")).hostname or "").lower()
    parts = host.split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and len(parts[-2]) <= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def convert_all(raw: dict[str, dict]) -> list[dict]:
    """Every rule from every source, in priority order, without the blocked categories."""
    rules = []
    for source in PRIORITY:
        if source in raw:
            rules += [r for r in CONVERTERS[source](raw[source]) if r["category"] not in BLOCKED_CATEGORIES]
    return rules


def dedupe(rules: list[dict]) -> list[dict]:
    """Drops sites already covered by a higher-priority source (same domain).

    Within one source every rule is kept: WhatsMyName, for instance, has separate GitHub user and gist checks.
    Dedupe *after* validation, so a site whose best rule broke can still be covered by another source's rule.
    """
    order = {s: i for i, s in enumerate(PRIORITY)}
    owner: dict[str, str] = {}
    for r in sorted(rules, key=lambda r: order[r["source"]]):
        owner.setdefault(site_domain(r["profile_url"]), r["source"])
    # Mastodon and Lemmy instances share software, not domains, so they never collide here.
    return [r for r in rules if owner[site_domain(r["profile_url"])] == r["source"]]


def merge(raw: dict[str, dict]) -> list[dict]:
    """Converts all sources and removes duplicates (no validation)."""
    return dedupe(convert_all(raw))


def rule_id(rule: dict) -> str:
    return f"{rule['source']}:{rule['name']}"


def username_allowed(rule: dict, username: str) -> bool:
    regex = rule.get("regex")
    if not regex:
        return True
    try:
        return re.search(regex, username) is not None
    except re.error:
        return True

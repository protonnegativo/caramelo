"""Pull profile details out of the response that was already downloaded to confirm the profile.

No extractor makes an extra request: sites that answer with JSON (GitHub, GitLab, Keybase, Mastodon...)
have a dedicated extractor; everything else goes through the page meta-tag extractor.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from collections.abc import Callable

Details = dict  # Profile fields: name, bio, avatar, location, created_at, followers, links, linked_accounts, extra

# --- helpers -----------------------------------------------------------------

_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
_TAG = re.compile(r"<[^>]+>")

#: How to recognize an account on another network from a link.
_NETWORKS = [
    ("github", r"github\.com/([A-Za-z0-9-]{1,39})(?:/?$|[?#])"),
    ("gitlab", r"gitlab\.com/([A-Za-z0-9_.-]+)/?$"),
    ("twitter", r"(?:twitter|x)\.com/(?!home|intent|share|search)@?([A-Za-z0-9_]{1,15})/?$"),
    ("instagram", r"instagram\.com/(?!p/|reel/|explore/)([A-Za-z0-9_.]{1,30})/?$"),
    ("tiktok", r"tiktok\.com/@([A-Za-z0-9_.]{2,24})/?$"),
    ("youtube", r"youtube\.com/@([A-Za-z0-9_.-]{3,30})/?$"),
    ("linkedin", r"linkedin\.com/in/([A-Za-z0-9_-]{3,100})/?$"),
    ("telegram", r"(?:t\.me|telegram\.me)/([A-Za-z0-9_]{5,32})/?$"),
    ("twitch", r"twitch\.tv/([A-Za-z0-9_]{4,25})/?$"),
    ("reddit", r"reddit\.com/(?:u|user)/([A-Za-z0-9_-]{3,20})/?$"),
    ("bluesky", r"bsky\.app/profile/([A-Za-z0-9_.-]+)/?$"),
    ("keybase", r"keybase\.io/([A-Za-z0-9_]{2,16})/?$"),
    ("linktree", r"linktr\.ee/([A-Za-z0-9_.]{1,30})/?$"),
]
_NETWORKS = [(network, re.compile(pattern, re.I)) for network, pattern in _NETWORKS]


def clean(text: str | None, limit: int = 500) -> str | None:
    if not text:
        return None
    text = html.unescape(_TAG.sub(" ", str(text)))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] or None


def links_in(*texts: str | None) -> list[str]:
    seen: list[str] = []
    for t in texts:
        for url in _URL.findall(html.unescape(t or "")):
            url = url.rstrip(".,;:")
            if url not in seen:
                seen.append(url)
    return seen


def accounts_in(links: list[str]) -> dict[str, str]:
    accounts: dict[str, str] = {}
    for link in links:
        for network, pattern in _NETWORKS:
            m = pattern.search(link)
            if m and network not in accounts:
                accounts[network] = m.group(1)
    return accounts


def _date(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()
    return str(value)[:10]


def _json(text: str):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _with_links(d: Details, *texts: str | None, extra: list[str] | None = None) -> Details:
    links = [l for l in (extra or []) if l] + links_in(*texts)
    d["links"] = list(dict.fromkeys(links))
    d["linked_accounts"] = {**accounts_in(d["links"]), **d.get("linked_accounts", {})}
    return d


# --- generic extractor: HTML page meta tags ----------------------------------

_META = re.compile(r"<meta\s[^>]*>", re.I)
_ATTR = re.compile(r'([a-zA-Z:_-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def meta_tags(page: str) -> dict[str, str]:
    metas: dict[str, str] = {}
    for tag in _META.findall(page[:300_000]):
        attrs = {m.group(1).lower(): m.group(3) if m.group(3) is not None else m.group(4) for m in _ATTR.finditer(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key and "content" in attrs and key not in metas:
            metas[key] = attrs["content"]
    return metas


def from_page(text: str, site: str) -> Details:
    if not text or text.lstrip()[:1] in "{[":
        return {}
    metas = meta_tags(text)
    title = metas.get("og:title") or metas.get("twitter:title")
    if not title:
        m = _TITLE.search(text[:300_000])
        title = m.group(1) if m else None
    name = _name_from_title(clean(title, 120), site)
    bio = clean(metas.get("og:description") or metas.get("description") or metas.get("twitter:description"))
    if bio and _is_boilerplate(bio, site):
        bio = None
    avatar = metas.get("og:image") or metas.get("twitter:image")
    return _with_links({"name": name, "bio": bio, "avatar": html.unescape(avatar) if avatar else None}, bio)


def _site_words(site: str) -> set[str]:
    base = re.sub(r"\(.*?\)", "", site).casefold()
    return {p for p in re.split(r"[^a-z0-9]+", base) if len(p) > 2}


def _name_from_title(title: str | None, site: str) -> str | None:
    """"Jane (@jane) • Instagram" → "Jane (@jane)"; "Steam Community :: Jane" → "Jane"."""
    if not title:
        return None
    name = re.split(r"\s+[|•·–—-]\s+", title)[0]
    name = re.sub(r"^.{0,40}?::\s*", "", name)
    name = re.sub(r"(?i)'s (profile|page|channel)\b.*$", "", name)
    name = re.sub(r"(?i)^(profile|perfil|user|usuário)( of| de)?\s*[:-]?\s*", "", name)
    prefix = re.match(r"^([^:]{2,40}):\s+(.+)$", name)
    if prefix and _site_words(site) & _site_words(prefix.group(1)):
        name = prefix.group(2)
    name = name.strip()
    if not name or _site_words(name) and _site_words(name) <= _site_words(site):
        return None
    return name


def _is_boilerplate(text: str, site: str) -> bool:
    """Default descriptions a site generates for every profile ("Follow X on Y", "profile on Y")."""
    t = text.casefold()
    if any(w in t for w in _site_words(site)):
        return True
    return bool(re.search(r"(?i)\b(profile (of|for|on)|overview of|follow \S+ on|you can contact @|"
                          r"join \S+ on|sign up|log ?in)\b", text))


# --- JSON API extractors -----------------------------------------------------

def github(text: str, username: str) -> Details:
    j = _json(text) or {}
    accounts = {"twitter": j["twitter_username"]} if j.get("twitter_username") else {}
    d = {
        "name": j.get("name"), "bio": clean(j.get("bio")), "avatar": j.get("avatar_url"),
        "location": j.get("location"), "created_at": _date(j.get("created_at")), "followers": j.get("followers"),
        "linked_accounts": accounts,
        "extra": {k: j[k] for k in ("company", "public_repos", "hireable") if j.get(k) not in (None, "")},
    }
    blog = j.get("blog") or None
    if blog and not blog.startswith("http"):
        blog = "https://" + blog
    return _with_links(d, j.get("bio"), extra=[blog])


def gitlab(text: str, username: str) -> Details:
    j = _json(text)
    j = j[0] if isinstance(j, list) and j else {}
    return {"name": j.get("name"), "avatar": j.get("avatar_url"), "extra": {"id": j["id"]} if j.get("id") else {}}


def codeberg(text: str, username: str) -> Details:
    j = _json(text) or {}
    d = {"name": j.get("full_name") or None, "bio": clean(j.get("description")), "avatar": j.get("avatar_url"),
         "location": j.get("location") or None, "created_at": _date(j.get("created")), "followers": j.get("followers_count")}
    return _with_links(d, j.get("description"), extra=[j.get("website") or None])


def keybase(text: str, username: str) -> Details:
    j = _json(text) or {}
    them = (j.get("them") or [{}])[0] or {}
    profile = them.get("profile") or {}
    proofs = (them.get("proofs_summary") or {}).get("all") or []
    accounts = {p["proof_type"]: p["nametag"] for p in proofs if p.get("proof_type") and p.get("nametag")}
    links = [p.get("service_url") for p in proofs if p.get("service_url")]
    d = {"name": profile.get("full_name"), "bio": clean(profile.get("bio")), "location": profile.get("location"),
         "created_at": _date((them.get("basics") or {}).get("ctime")), "linked_accounts": accounts,
         "extra": {"verified_proofs": len(proofs)} if proofs else {}}
    return _with_links(d, profile.get("bio"), extra=links)


def hacker_news(text: str, username: str) -> Details:
    j = _json(text) or {}
    return _with_links({"bio": clean(j.get("about")), "created_at": _date(j.get("created")),
                        "extra": {"karma": j.get("karma")} if j.get("karma") is not None else {}}, j.get("about"))


def chess_com(text: str, username: str) -> Details:
    j = _json(text) or {}
    country = (j.get("country") or "").rsplit("/", 1)[-1] or None
    return {"name": j.get("name"), "avatar": j.get("avatar"), "location": j.get("location") or country,
            "created_at": _date(j.get("joined")), "followers": j.get("followers")}


def dev_to(text: str, username: str) -> Details:
    j = _json(text) or {}
    accounts = {k: j[f"{k}_username"] for k in ("github", "twitter") if j.get(f"{k}_username")}
    d = {"name": j.get("name"), "bio": clean(j.get("summary")), "avatar": j.get("profile_image"),
         "location": j.get("location") or None, "created_at": _date(j.get("joined_at")), "linked_accounts": accounts}
    return _with_links(d, j.get("summary"), extra=[j.get("website_url") or None])


def docker_hub(text: str, username: str) -> Details:
    j = _json(text) or {}
    return _with_links({"name": j.get("full_name") or None, "location": j.get("location") or None,
                        "created_at": _date(j.get("date_joined")), "avatar": j.get("gravatar_url") or None},
                       extra=[j.get("profile_url") or None])


def bluesky(text: str, username: str) -> Details:
    j = _json(text) or {}
    d = {"name": j.get("displayName"), "bio": clean(j.get("description")), "avatar": j.get("avatar"),
         "created_at": _date(j.get("createdAt")), "followers": j.get("followersCount")}
    return _with_links(d, j.get("description"))


def gravatar(text: str, username: str) -> Details:
    j = _json(text) or {}
    e = (j.get("entry") or [{}])[0] or {}
    accounts = {a.get("shortname"): a.get("username") for a in e.get("accounts", []) if a.get("shortname") and a.get("username")}
    links = [a.get("url") for a in e.get("accounts", [])] + [u.get("value") for u in e.get("urls", [])]
    d = {"name": e.get("displayName"), "bio": clean(e.get("aboutMe")), "avatar": e.get("thumbnailUrl"),
         "location": e.get("currentLocation"), "linked_accounts": accounts}
    return _with_links(d, e.get("aboutMe"), extra=[l for l in links if l])


def mastodon(text: str, username: str) -> Details:
    j = _json(text) or {}
    if isinstance(j.get("accounts"), list):  # /api/v2/search
        j = j["accounts"][0] if j["accounts"] else {}
    fields = j.get("fields") or []
    links = links_in(*(f.get("value") for f in fields))
    d = {"name": j.get("display_name") or None, "bio": clean(j.get("note")), "avatar": j.get("avatar"),
         "created_at": _date(j.get("created_at")), "followers": j.get("followers_count")}
    return _with_links(d, j.get("note"), extra=links)


def duolingo(text: str, username: str) -> Details:
    j = _json(text) or {}
    u = (j.get("users") or [{}])[0] or {}
    return {"name": u.get("name"), "avatar": ("https:" + u["picture"] + "/xlarge") if u.get("picture") else None,
            "created_at": _date(u.get("creationDate")),
            "extra": {"courses": [c.get("title") for c in u.get("courses", []) if c.get("title")]} if u.get("courses") else {}}


#: Site name in the dataset → extractor. Mastodon is matched by name pattern (there are dozens of instances).
EXTRACTORS: dict[str, Callable[[str, str], Details]] = {
    "GitHub (User)": github,
    "GitLab": gitlab,
    "Codeberg": codeberg,
    "Keybase": keybase,
    "Hacker News": hacker_news,
    "Chess.com": chess_com,
    "dev.to": dev_to,
    "Docker Hub (User)": docker_hub,
    "Bluesky Username": bluesky,
    "Gravatar": gravatar,
    "Mastodon API": mastodon,
    "Duolingo": duolingo,
}


def extract(site: str, text: str, username: str) -> tuple[Details, str]:
    """Returns (details, source). Never raises: a broken extractor must not break the search."""
    fn = EXTRACTORS.get(site) or (mastodon if "(Mastodon Instance)" in site else None)
    try:
        if fn:
            return fn(text, username), f"api-{site.split(' ')[0].lower()}"
        return from_page(text, site), "page"
    except Exception:  # noqa: BLE001
        return {}, "page"

"""Runs the checks: tries each username on each site, concurrently, and builds the dossier."""
from __future__ import annotations

import asyncio
import time
from typing import Callable, Iterable

import httpx

from .extractors import extract
from .models import Dossier, Profile
from .sites import Site, load_sites
from .variants import looks_like_name, to_ascii, username_variants

#: Many sites return an error page or block clients that don't look like a browser.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

Progress = Callable[[int, int, "Profile | None"], None]
_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def profile_exists(site: Site, status: int, text: str) -> bool | None:
    """Reads a site's answer with its rule. None means the answer can't be trusted (captcha, rate limit...)."""
    if any(e in text for e in site.error_strings) or status == 429:
        return None
    if site.mode == "string":
        return status == site.exists_code and site.exists_string in text and not any(a in text for a in site.absence)
    ok = 200 <= status < 300 and status not in site.error_codes
    if site.mode in ("status", "redirect"):
        return ok
    if site.mode == "message":
        if any(a in text for a in site.absence):
            return False
        if site.presence:
            return any(p in text for p in site.presence)
        # Only absence texts to go on: an error status means no profile even if the page wording changed.
        return status < 400
    return False


async def fetch(client: httpx.AsyncClient, site: Site, account: str, timeout: float) -> httpx.Response:
    url = site.check_url.replace("{account}", account)
    body = site.body.replace("{account}", account) if site.body else None
    return await client.request(site.method, url, content=body, headers=site.headers, timeout=timeout,
                                follow_redirects=site.mode != "redirect")


async def check(client: httpx.AsyncClient, site: Site, username: str, timeout: float) -> tuple[Profile | None, bool]:
    """Tries one username on one site. Returns (profile or None, did the site give a usable answer?)."""
    account = site.prepare(username)
    if not site.accepts(account):
        return None, True  # the site can't have this username (too short, invalid characters...)
    try:
        r = await fetch(client, site, account, timeout)
    except (httpx.HTTPError, UnicodeError, ValueError):
        return None, False
    text = r.text if site.method != "HEAD" else ""
    exists = profile_exists(site, r.status_code, text)
    if exists is None:
        return None, False
    if not exists:
        return None, True
    details, source = extract(site.name, text, account)
    profile = Profile(site=site.name, url=site.url(account), username=account, category=site.category,
                      source=source, found_by=site.source)
    for key, value in details.items():
        if value not in (None, "", [], {}):
            setattr(profile, key, value)
    return profile, True


async def investigate_async(
    target: str,
    *,
    usernames: Iterable[str] | None = None,
    categories: set[str] | None = None,
    sites: set[str] | None = None,
    sources: set[str] | None = None,
    pivot: bool = True,
    max_pivots: int = 5,
    concurrency: int = 50,
    timeout: float = 15.0,
    progress: Progress | None = None,
    client: httpx.AsyncClient | None = None,
) -> Dossier:
    """Async version of :func:`investigate` (use it inside a running event loop)."""
    started = time.perf_counter()
    is_name = looks_like_name(target)
    to_try = list(usernames) if usernames else (username_variants(target) if is_name else [target.strip().lstrip("@")])
    site_list = load_sites(categories, sites, sources)
    dossier = Dossier(target=target, usernames_tried=[])

    own_client = client is None
    client = client or httpx.AsyncClient(
        follow_redirects=True, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
    )
    limit = asyncio.Semaphore(concurrency)
    total = {"checks": len(to_try) * len(site_list)}  # grows when pivots are added
    done = 0

    async def run_round(round_usernames: list[str], confidence: str, via: str | None) -> None:
        async def one(site: Site, username: str) -> None:
            nonlocal done
            async with limit:
                profile, answered = await check(client, site, username, timeout)
            done += 1
            if not answered:
                dossier.no_response.append(f"{site.name} ({username})")
            if profile:
                profile.confidence = confidence
                profile.via = via if via else (username if username != target else None)
                if confidence == "low" and _name_matches(profile.name, target):
                    profile.confidence = "medium"
                dossier.profiles.append(profile)
            if progress:
                progress(done, total["checks"], profile)

        await asyncio.gather(*(one(s, u) for u in round_usernames for s in site_list))
        dossier.usernames_tried += round_usernames
        dossier.checks += len(round_usernames) * len(site_list)

    try:
        await run_round(to_try, "low" if is_name else "high", None)
        if pivot:
            new = _pivots(dossier, max_pivots)
            if new:
                total["checks"] += len(new) * len(site_list)
                # Accounts mentioned by a confirmed profile: same person, but worth showing where they came from.
                await asyncio.gather(*(
                    run_round([username], "medium" if is_name else "high", f"{username} (mentioned on {origin})")
                    for username, origin in new.items()
                ))
    finally:
        if own_client:
            await client.aclose()

    dossier.profiles.sort(key=lambda p: (_CONFIDENCE_ORDER[p.confidence], p.site.lower()))
    dossier.duration_s = round(time.perf_counter() - started, 1)
    return dossier


def investigate(target: str, **options) -> Dossier:
    """Finds the public profiles of a username (or a real name, e.g. "Maria Souza") on hundreds of sites.

    Needs no API key and never contacts the person being searched. Example::

        from caramelo import investigate
        dossier = investigate("johndoe")
        for profile in dossier.profiles:
            print(profile.site, profile.url)

    Options: ``categories``, ``sites`` and ``sources`` (filters; sources are "whatsmyname", "sherlock",
    "maigret"), ``pivot`` (follow accounts mentioned on the profiles),
    ``max_pivots``, ``concurrency``, ``timeout`` and ``progress`` (called after every check).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(investigate_async(target, **options))
    raise RuntimeError("An event loop is already running (e.g. Jupyter). Use: await investigate_async(...)")


def _pivots(dossier: Dossier, maximum: int) -> dict[str, str]:
    """Usernames not tried yet that the found profiles mention (e.g. the Twitter handle on GitHub)."""
    tried = {u.casefold() for u in dossier.usernames_tried}
    new: dict[str, str] = {}
    for p in dossier.profiles:
        if p.confidence == "low":
            continue
        for _network, username in p.linked_accounts.items():
            username = username.strip().lstrip("@").split(".bsky.social")[0]
            if 3 <= len(username) <= 40 and username.casefold() not in tried and username not in new:
                new[username] = p.site
    return dict(list(new.items())[:maximum])


def _name_matches(profile_name: str | None, searched_name: str) -> bool:
    if not profile_name:
        return False
    profile = to_ascii(profile_name).casefold()
    parts = [p for p in to_ascii(searched_name).casefold().split() if len(p) > 2]
    return len(parts) >= 2 and parts[0] in profile and parts[-1] in profile

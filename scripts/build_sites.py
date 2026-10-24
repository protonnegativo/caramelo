"""Builds src/caramelo/data/sites.json: merges the three sources and keeps only the sites that pass a live check.

For every site it checks a username the source lists as existing (it must be found) and a random username
(it must not be found). Sites that fail either test, or never answer, are left out and listed in "excluded".

    python scripts/build_sites.py              # download the sources and validate (takes a few minutes)
    python scripts/build_sites.py --no-check   # merge only, no network validation
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import string
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from caramelo.engine import USER_AGENT, fetch, profile_exists
from caramelo.sites import Site, download_sources
from caramelo.sources import convert_all, dedupe, rule_id

OUT = Path(__file__).resolve().parents[1] / "src" / "caramelo" / "data" / "sites.json"


def random_username(site: Site) -> str | None:
    rng = random.Random(site.name)
    candidates = [site.unclaimed] if site.unclaimed else []
    candidates += ["caramelo" + "".join(rng.choices(string.ascii_lowercase, k=10)), "noonewouldeverusethis7",
                   "zq" + "".join(rng.choices(string.ascii_lowercase + string.digits, k=8))]
    return next((u for u in candidates if u and site.accepts(u)), None)


async def answer(client, site: Site, username: str, timeout: float) -> bool | None:
    try:
        r = await fetch(client, site, site.prepare(username), timeout)
    except (httpx.HTTPError, UnicodeError, ValueError):
        return None
    return profile_exists(site, r.status_code, r.text if site.method != "HEAD" else "")


async def validate(site: Site, client, limit, timeout: float) -> str:
    """Returns "ok" or the reason the site was left out."""
    known = next((u for u in site.known if site.accepts(site.prepare(u))), None)
    unknown = random_username(site)
    if not known:
        return "no known username to test with"
    if not unknown:
        return "no random username fits its rules"
    async with limit:
        found = await answer(client, site, known, timeout)
        if found is None:
            return "no usable answer"
        if not found:
            return "known username not found"
        missing = await answer(client, site, unknown, timeout)
    if missing is None:
        return "no usable answer"
    if missing:
        return "random username reported as found (false positive)"
    return "ok"


async def run(rules: list[dict], concurrency: int, timeout: float) -> tuple[list[dict], dict[str, str]]:
    sites = [Site.from_rule(r) for r in rules]
    limit = asyncio.Semaphore(concurrency)
    client = httpx.AsyncClient(headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
                               limits=httpx.Limits(max_connections=concurrency), verify=True)
    results: dict[str, str] = {}
    done = 0
    started = time.perf_counter()

    async def one(site: Site, rule: dict) -> None:
        nonlocal done
        try:
            results[rule_id(rule)] = await validate(site, client, limit, timeout)
        except Exception as e:  # noqa: BLE001 - one odd site must not stop the build
            results[rule_id(rule)] = f"error: {type(e).__name__}"
        done += 1
        if done % 250 == 0 or done == len(sites):
            ok = sum(v == "ok" for v in results.values())
            print(f"  {done}/{len(sites)} checked · {ok} ok · {time.perf_counter() - started:.0f}s", flush=True)

    try:
        await asyncio.gather(*(one(s, r) for s, r in zip(sites, rules)))
        # Second chance for sites that didn't answer: often just a slow server or a hiccup.
        retry = [(s, r) for s, r in zip(sites, rules) if results[rule_id(r)] == "no usable answer"]
        if retry:
            print(f"  retrying {len(retry)} sites that didn't answer…", flush=True)
            for s, r in retry:
                results[rule_id(r)] = "retry"
            done = len(sites) - len(retry)
            await asyncio.gather(*(one(s, r) for s, r in retry))
    finally:
        await client.aclose()
    kept = [r for r in rules if results[rule_id(r)] == "ok"]
    return kept, {k: v for k, v in results.items() if v != "ok"}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--no-check", action="store_true", help="merge only, skip the live validation")
    p.add_argument("--concurrency", type=int, default=80)
    p.add_argument("--timeout", type=float, default=15)
    a = p.parse_args()

    print("Downloading WhatsMyName, Sherlock and Maigret…", flush=True)
    rules = convert_all(download_sources())
    by_source = {s: sum(r["source"] == s for r in rules) for s in ("whatsmyname", "sherlock", "maigret")}
    print(f"{len(rules)} rules before validation: {by_source}", flush=True)

    excluded: dict[str, str] = {}
    if not a.no_check:
        # Validate every source's rule first, then dedupe: if one source's rule for a site is broken,
        # another source's working rule for the same site takes its place.
        rules, excluded = asyncio.run(run(rules, a.concurrency, a.timeout))
    before = len(rules)
    rules = dedupe(rules)
    print(f"Removed {before - len(rules)} duplicates (same site in more than one list)", flush=True)
    kept = {s: sum(r["source"] == s for r in rules) for s in ("whatsmyname", "sherlock", "maigret")}
    data = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "validated": not a.no_check,
            "sites": sorted(rules, key=lambda r: (r["source"], r["name"].lower())), "excluded": sorted(excluded)}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    reasons: dict[str, int] = {}
    for reason in excluded.values():
        reasons[reason] = reasons.get(reason, 0) + 1
    print(f"\nKept {len(rules)} sites: {kept}")
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  left out {n:5d} · {reason}")
    print(f"Saved {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())

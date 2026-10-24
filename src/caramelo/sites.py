"""The site list: rules from WhatsMyName, Sherlock and Maigret, merged and validated (see sources.py).

The validated list ships with the package (data/sites.json). `update_sites()` downloads the three sources
again and keeps the sites that passed validation, so rule fixes from upstream arrive without a new release.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

import httpx

from .sources import BLOCKED_CATEGORIES, URLS, convert_all, dedupe, rule_id, username_allowed


@dataclass(frozen=True)
class Site:
    name: str
    source: str
    category: str
    mode: str
    check_url: str
    profile_url: str
    method: str = "GET"
    body: str | None = None
    headers: dict[str, str] = field(default_factory=dict, hash=False, compare=False)
    exists_code: int = 200
    exists_string: str = ""
    presence: tuple[str, ...] = ()
    absence: tuple[str, ...] = ()
    error_codes: tuple[int, ...] = ()
    error_strings: tuple[str, ...] = ()
    regex: str | None = None
    strip_chars: str = ""
    known: tuple[str, ...] = ()
    unclaimed: str | None = None

    @classmethod
    def from_rule(cls, r: dict) -> "Site":
        tuples = ("presence", "absence", "error_codes", "error_strings", "known")
        return cls(**{k: tuple(v) if k in tuples else v for k, v in r.items() if k in cls.__dataclass_fields__})

    def url(self, username: str) -> str:
        """Profile URL to show to the user."""
        return self.profile_url.replace("{account}", username)

    def prepare(self, username: str) -> str:
        for c in self.strip_chars:
            username = username.replace(c, "")
        return username

    def accepts(self, username: str) -> bool:
        """False when the site's username rules (length, characters) can't match this username."""
        return username_allowed({"regex": self.regex}, username)


def cache_dir() -> Path:
    base = os.environ.get("CARAMELO_CACHE") or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "caramelo"


def _bundled() -> dict:
    return json.loads(resources.files("caramelo").joinpath("data/sites.json").read_text(encoding="utf-8"))


def _read_data() -> dict:
    """Uses the list downloaded by `update_sites()` when present; otherwise the one bundled with the package."""
    cached = cache_dir() / "sites.json"
    if cached.exists():
        try:
            return json.loads(cached.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return _bundled()


def load_sites(categories: set[str] | None = None, sites: set[str] | None = None,
               sources: set[str] | None = None) -> list[Site]:
    """Lists the sites to check. `categories`, `sites` (names, case-insensitive) and `sources` narrow the list."""
    names = {s.casefold() for s in sites} if sites else None
    result = []
    for r in _read_data()["sites"]:
        if r["category"] in BLOCKED_CATEGORIES:
            continue
        if categories and r["category"] not in categories:
            continue
        if names and r["name"].casefold() not in names:
            continue
        if sources and r["source"] not in sources:
            continue
        result.append(Site.from_rule(r))
    return result


def available_categories() -> list[str]:
    return sorted({r["category"] for r in _read_data()["sites"]} - BLOCKED_CATEGORIES)


def list_info() -> dict:
    """When the list was generated and how many sites came from each source."""
    data = _read_data()
    counts: dict[str, int] = {}
    for r in data["sites"]:
        counts[r["source"]] = counts.get(r["source"], 0) + 1
    return {"generated": data.get("generated"), "sites": len(data["sites"]), "by_source": counts}


def download_sources(timeout: float = 60) -> dict[str, dict]:
    raw = {}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for source, url in URLS.items():
            r = client.get(url)
            r.raise_for_status()
            raw[source] = r.json()
    return raw


def update_sites(timeout: float = 60) -> int:
    """Downloads the three sources again into the local cache. Returns how many sites the new list has.

    Sites that failed validation stay out. New Sherlock/Maigret sites wait for the next validated release;
    WhatsMyName sites (curated by hand upstream) are taken right away.
    """
    bundled = _bundled()
    validated = {rule_id(r) for r in bundled["sites"]}
    excluded = set(bundled.get("excluded", []))
    rules = dedupe([r for r in convert_all(download_sources(timeout))
                    if rule_id(r) not in excluded and (rule_id(r) in validated or r["source"] == "whatsmyname")])
    target = cache_dir()
    target.mkdir(parents=True, exist_ok=True)
    data = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sites": rules,
            "excluded": sorted(excluded)}
    (target / "sites.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return len(rules)

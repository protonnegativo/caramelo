"""Site list: the WhatsMyName dataset (CC BY-SA 4.0), bundled with the package and updatable."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import httpx

DATA_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"

#: Categories that are never checked: looking someone up on dating or adult sites serves to expose
#: people far more than any legitimate investigation.
BLOCKED_CATEGORIES = frozenset({"dating", "xx NSFW xx"})


@dataclass(frozen=True)
class Site:
    name: str
    check_url: str
    category: str
    exists_code: int
    exists_string: str
    missing_code: int | None = None
    missing_string: str | None = None
    profile_url: str | None = None
    post_body: str | None = None
    headers: dict[str, str] = field(default_factory=dict, hash=False, compare=False)
    strip_chars: str = ""
    known: tuple[str, ...] = ()

    def url(self, username: str) -> str:
        """Profile URL to show to the user."""
        return (self.profile_url or self.check_url).replace("{account}", username)

    def prepare(self, username: str) -> str:
        for c in self.strip_chars:
            username = username.replace(c, "")
        return username


def cache_dir() -> Path:
    base = os.environ.get("CARAMELO_CACHE") or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "caramelo"


def _read_data() -> dict:
    """Uses the list downloaded by `update_sites()` when present; otherwise the one bundled with the package."""
    cached = cache_dir() / "wmn-data.json"
    if cached.exists():
        try:
            return json.loads(cached.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return json.loads(resources.files("caramelo").joinpath("data/wmn-data.json").read_text(encoding="utf-8"))


def load_sites(categories: set[str] | None = None, sites: set[str] | None = None) -> list[Site]:
    """Lists the sites to check.

    `categories` and `sites` (site names, case-insensitive) narrow the list when given.
    """
    names = {s.casefold() for s in sites} if sites else None
    result = []
    for s in _read_data()["sites"]:
        if s.get("valid") is False or s.get("cat") in BLOCKED_CATEGORIES:
            continue
        if categories and s.get("cat") not in categories:
            continue
        if names and s["name"].casefold() not in names:
            continue
        result.append(
            Site(
                name=s["name"],
                check_url=s["uri_check"],
                category=s.get("cat", ""),
                exists_code=int(s["e_code"]),
                exists_string=s["e_string"],
                missing_code=int(s["m_code"]) if s.get("m_code") is not None else None,
                missing_string=s.get("m_string"),
                profile_url=s.get("uri_pretty"),
                post_body=s.get("post_body"),
                headers=s.get("headers") or {},
                strip_chars=s.get("strip_bad_char", ""),
                known=tuple(s.get("known", ())),
            )
        )
    return result


def available_categories() -> list[str]:
    return sorted(set(_read_data()["categories"]) - BLOCKED_CATEGORIES)


def update_sites(timeout: float = 30) -> int:
    """Downloads the latest site list into the local cache. Returns how many sites it has."""
    r = httpx.get(DATA_URL, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    data = r.json()
    target = cache_dir()
    target.mkdir(parents=True, exist_ok=True)
    (target / "wmn-data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return len(data["sites"])

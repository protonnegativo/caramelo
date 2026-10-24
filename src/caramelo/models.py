"""Data structures returned by an investigation."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class Profile:
    """A public profile found on one site."""

    site: str
    url: str
    username: str
    category: str = ""
    #: "high" when the site confirmed the profile through the page content; "medium"/"low" when the
    #: username was derived from a real name (it may belong to someone else).
    confidence: str = "high"
    name: str | None = None
    bio: str | None = None
    avatar: str | None = None
    location: str | None = None
    created_at: str | None = None
    followers: int | None = None
    links: list[str] = field(default_factory=list)
    #: Accounts on other networks that this profile reveals, e.g. {"twitter": "jdoe"}.
    linked_accounts: dict[str, str] = field(default_factory=dict)
    extra: dict[str, object] = field(default_factory=dict)
    #: Where the details came from: "page" (meta tags) or the extractor name (e.g. "api-github").
    source: str = "page"
    #: Which site list supplied the rule that found this profile: "whatsmyname", "sherlock" or "maigret".
    found_by: str = ""
    #: Username that led to this profile, when it differs from the target (e.g. found through a pivot).
    via: str | None = None


@dataclass
class Dossier:
    """Result of `investigate()`: every profile found for a target."""

    target: str
    usernames_tried: list[str]
    profiles: list[Profile] = field(default_factory=list)
    checks: int = 0
    no_response: list[str] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    duration_s: float = 0.0

    # --- summaries -------------------------------------------------------
    def names(self) -> list[str]:
        """Display names found on the profiles, most frequent first (excluding names that are just the username)."""
        usernames = {p.username.casefold() for p in self.profiles} | {u.casefold() for u in self.usernames_tried}
        return _by_frequency(p.name for p in self.profiles if p.name and p.name.strip().casefold() not in usernames)

    def locations(self) -> list[str]:
        return _by_frequency(p.location for p in self.profiles if p.location)

    def links(self) -> list[str]:
        """External links mentioned on the profiles (personal sites, other networks)."""
        return _by_frequency(link for p in self.profiles for link in p.links)

    def linked_accounts(self) -> dict[str, set[str]]:
        accounts: dict[str, set[str]] = {}
        for p in self.profiles:
            for network, username in p.linked_accounts.items():
                accounts.setdefault(network, set()).add(username)
        return accounts

    def by_category(self) -> dict[str, list[Profile]]:
        groups: dict[str, list[Profile]] = {}
        for p in sorted(self.profiles, key=lambda p: p.site.lower()):
            groups.setdefault(p.category or "other", []).append(p)
        return dict(sorted(groups.items(), key=lambda kv: -len(kv[1])))

    # --- export ----------------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["summary"] = {
            "profiles": len(self.profiles),
            "names": self.names(),
            "locations": self.locations(),
            "links": self.links(),
            "linked_accounts": {k: sorted(v) for k, v in self.linked_accounts().items()},
        }
        return d

    def to_json(self, **kwargs) -> str:
        kwargs.setdefault("ensure_ascii", False)
        kwargs.setdefault("indent", 2)
        return json.dumps(self.to_dict(), **kwargs)


def _by_frequency(values) -> list[str]:
    counts: dict[str, int] = {}
    original: dict[str, str] = {}
    for v in values:
        key = v.strip().casefold()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
        original.setdefault(key, v.strip())
    return [original[k] for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])]

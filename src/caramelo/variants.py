"""Derives likely usernames from a real name ("John da Silva" → johnsilva, john.silva, jsilva...)."""
from __future__ import annotations

import re
import unicodedata

#: Name particles skipped when building usernames (Portuguese, Spanish, Dutch, German, French, Italian).
_PARTICLES = {"da", "de", "do", "das", "dos", "e", "di", "du", "van", "von", "der", "del", "la", "le", "y"}


def to_ascii(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def looks_like_name(text: str) -> bool:
    """A target with a space (e.g. "Maria Souza") is treated as a real name; without one, as a username."""
    return " " in text.strip()


def username_variants(name: str, limit: int = 12) -> list[str]:
    parts = [p for p in re.split(r"[^a-z0-9]+", to_ascii(name).lower()) if p and p not in _PARTICLES]
    if not parts:
        return []
    if len(parts) == 1:
        return parts
    first, last = parts[0], parts[-1]
    candidates = [
        first + last, f"{first}.{last}", f"{first}_{last}", f"{first}-{last}",
        first[0] + last, f"{first[0]}.{last}", first + last[0], last + first,
        f"{last}.{first}", "".join(parts), first[0] + "".join(p[0] for p in parts[1:-1]) + last,
    ]
    if len(parts) > 2:
        candidates += [first + parts[1], f"{first}.{parts[1]}"]
    return [c for c in dict.fromkeys(candidates) if len(c) >= 3][:limit]

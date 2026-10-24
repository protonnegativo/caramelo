"""Command line: caramelo <username or "first last"> [--json] [--html FILE] [--silent]."""
from __future__ import annotations

import argparse
import sys
from contextlib import nullcontext
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn

from . import __version__, banner
from .engine import investigate
from .report import to_html, to_terminal
from .sites import available_categories, list_info, load_sites, update_sites
from .sources import PRIORITY


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="caramelo",
        description="Finds the public profiles of a username (or real name) on thousands of sites, no API keys required.",
        epilog='Examples: caramelo johndoe · caramelo "Maria Souza" · caramelo johndoe --html dossier.html'
               " · caramelo johndoe --silent | grep github",
    )
    p.add_argument("target", nargs="?", help='username (e.g. johndoe) or a quoted real name (e.g. "Maria Souza")')
    p.add_argument("--json", action="store_true", help="print the dossier as JSON (for other programs)")
    p.add_argument("--html", metavar="FILE", help="save an HTML report")
    p.add_argument("-q", "--silent", action="store_true",
                   help="no banner, progress or tables: print one 'site<TAB>url' line per profile found "
                        "(with --json, only the JSON)")
    p.add_argument("-c", "--category", action="append", metavar="CAT", help="only sites in this category (repeatable)")
    p.add_argument("-s", "--site", action="append", metavar="SITE", help="only this site (repeatable)")
    p.add_argument("--source", action="append", choices=PRIORITY,
                   help="only sites from this list (repeatable): whatsmyname, sherlock or maigret")
    p.add_argument("--no-pivot", action="store_true", help="don't follow accounts mentioned on the profiles found")
    p.add_argument("--timeout", type=float, default=15, help="seconds per site (default: 15)")
    p.add_argument("--concurrency", type=int, default=50, help="simultaneous checks (default: 50)")
    p.add_argument("--categories", action="store_true", help="list the categories and exit")
    p.add_argument("--update", action="store_true", help="download the latest site lists and exit")
    p.add_argument("--no-banner", action="store_true", help="don't print the startup banner")
    p.add_argument("--version", action="version", version=f"caramelo {__version__}")
    a = p.parse_args(argv)

    err = Console(stderr=True, quiet=a.silent)
    # The banner goes to stderr, so `--json > file` stays clean even when it is shown.
    if not (a.json or a.no_banner or a.categories or a.silent):
        banner.show(err, sites=len(load_sites()), version=__version__)
    if a.update:
        total = update_sites()
        by_source = " · ".join(f"{n} {s}" for s, n in list_info()["by_source"].items())
        err.print(f"Site list updated: {total} sites ({by_source}).")
        return 0
    if a.categories:
        print("\n".join(available_categories()))
        return 0
    if not a.target:
        p.print_help()
        return 2
    if not a.target.strip().lstrip("@").strip():
        Console(stderr=True).print("Give a username (e.g. johndoe) or a quoted name (e.g. \"Maria Souza\").")
        return 2

    categories = set(a.category) if a.category else None
    sites = set(a.site) if a.site else None
    sources = set(a.source) if a.source else None
    total_sites = len(load_sites(categories, sites, sources))
    if total_sites == 0:
        Console(stderr=True).print("No site matches the filters. See: caramelo --categories")
        return 2

    bar = None if a.silent else Progress(
        TextColumn("[bold]{task.description}"), BarColumn(), MofNCompleteColumn(),
        TextColumn("· {task.fields[found]} profiles"), TimeElapsedColumn(), console=err, transient=True)
    with bar or nullcontext():
        task = bar.add_task(f"Sniffing out {escape(a.target)}", total=total_sites, found=0) if bar else None
        found = 0

        def progress(done: int, total: int, profile) -> None:
            nonlocal found
            found += profile is not None
            bar.update(task, completed=done, total=total, found=found)

        dossier = investigate(
            a.target, categories=categories, sites=sites, sources=sources, pivot=not a.no_pivot,
            timeout=a.timeout, concurrency=a.concurrency, progress=progress if bar else None,
        )

    if a.json:
        sys.stdout.reconfigure(encoding="utf-8")
        print(dossier.to_json())
    elif a.silent:
        sys.stdout.reconfigure(encoding="utf-8")
        for profile in dossier.profiles:
            print(f"{profile.site}\t{profile.url}")
    else:
        to_terminal(dossier)
    if a.html:
        Path(a.html).write_text(to_html(dossier), encoding="utf-8")
        err.print(f"\nReport saved to {escape(str(Path(a.html).resolve()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

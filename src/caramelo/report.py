"""Prints the dossier to the terminal and renders the HTML report (a single self-contained file)."""
from __future__ import annotations

import html
from datetime import datetime

from rich.console import Console
from rich.table import Table

from .models import Dossier, Profile

_CONFIDENCE_COLOR = {"high": "green", "medium": "yellow", "low": "red"}


def to_terminal(d: Dossier, console: Console | None = None) -> None:
    console = console or Console()
    console.print()
    console.rule(f"[bold]Dossier: {d.target}")
    console.print(f"{len(d.profiles)} profiles from {d.checks} checks · {d.duration_s}s"
                  + (f" · {len(d.no_response)} without response" if d.no_response else ""))
    if len(d.usernames_tried) > 1:
        console.print(f"[dim]Usernames tried: {', '.join(d.usernames_tried)}")

    summary = [("Names", d.names()[:5]), ("Locations", d.locations()[:5]), ("Links", d.links()[:8])]
    accounts = d.linked_accounts()
    if accounts:
        summary.append(("Linked accounts", [f"{n}: {', '.join(sorted(u))}" for n, u in sorted(accounts.items())]))
    for title, items in summary:
        if items:
            console.print(f"\n[bold]{title}[/]")
            for item in items:
                console.print(f"  • {item}", highlight=False)

    for category, profiles in d.by_category().items():
        table = Table(title=f"{category} ({len(profiles)})", title_justify="left", expand=True)
        table.add_column("Site", style="bold", no_wrap=True)
        table.add_column("Profile", overflow="fold")
        table.add_column("Details", overflow="fold")
        table.add_column("", no_wrap=True)
        for p in profiles:
            table.add_row(p.site, p.url, _short_details(p),
                          f"[{_CONFIDENCE_COLOR[p.confidence]}]{p.confidence}[/]\n[dim]{p.found_by}")
        console.print()
        console.print(table)
    if any(p.confidence != "high" for p in d.profiles):
        console.print("\n[dim]Medium/low confidence: the username exists, but it may belong to someone else. Verify before concluding.")


def _short_details(p: Profile) -> str:
    parts = [x for x in (p.name, p.location, f"since {p.created_at}" if p.created_at else None,
                         f"{p.followers} followers" if p.followers else None) if x]
    if p.bio:
        parts.append(p.bio[:90] + ("…" if len(p.bio) > 90 else ""))
    if p.via:
        parts.append(f"via {p.via}")
    return " · ".join(str(x) for x in parts)


def to_html(d: Dossier) -> str:
    e = html.escape
    when = datetime.fromisoformat(d.started_at).strftime("%Y-%m-%d %H:%M UTC")

    def bullet_list(items, link=False):
        if not items:
            return '<p class="empty">Nothing found.</p>'
        li = (f'<li><a href="{e(i)}" rel="noreferrer noopener" target="_blank">{e(i)}</a></li>' if link
              else f"<li>{e(i)}</li>" for i in items)
        return f"<ul>{''.join(li)}</ul>"

    def card(p: Profile) -> str:
        avatar = (f'<img src="{e(p.avatar)}" alt="" loading="lazy" referrerpolicy="no-referrer">'
                  if p.avatar and p.avatar.startswith("https://") else '<div class="no-avatar"></div>')
        rows = [f"<dt>{label}</dt><dd>{e(str(v))}</dd>" for label, v in (
            ("Name", p.name), ("Location", p.location), ("Since", p.created_at), ("Followers", p.followers), ("Via", p.via),
            ("Rule from", p.found_by)) if v]
        bio = f'<p class="bio">{e(p.bio)}</p>' if p.bio else ""
        links = "".join(f'<a href="{e(l)}" rel="noreferrer noopener" target="_blank">{e(l)}</a>' for l in p.links[:6])
        return (f'<article class="profile c-{p.confidence}">{avatar}<div class="body">'
                f'<header><h3>{e(p.site)}</h3><span class="conf">{p.confidence}</span></header>'
                f'<a class="url" href="{e(p.url)}" rel="noreferrer noopener" target="_blank">{e(p.url)}</a>'
                f'{bio}<dl>{"".join(rows)}</dl><div class="links">{links}</div></div></article>')

    accounts = [f"{n}: {', '.join(sorted(u))}" for n, u in sorted(d.linked_accounts().items())]
    sections = "".join(
        f'<section><h2>{e(cat)} <small>{len(ps)}</small></h2><div class="cards">{"".join(card(p) for p in ps)}</div></section>'
        for cat, ps in d.by_category().items())

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dossier: {e(d.target)}</title>
<style>
:root{{--bg:#f6f5f2;--card:#fff;--ink:#1d1f24;--muted:#6b6f78;--line:#e3e1dc;--high:#1f8a4c;--medium:#b7791f;--low:#c53030;--accent:#2b4acb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#121316;--card:#1b1d22;--ink:#eceef2;--muted:#9aa0ab;--line:#2c2f36;--accent:#8ea2ff}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:32px 16px 64px}}
h1{{font-size:34px;margin:0 0 4px;letter-spacing:-.01em}}.meta{{color:var(--muted);margin:0 0 28px}}
.summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px;margin-bottom:32px}}
.summary div{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-width:0}}
.summary h2{{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 6px}}
.summary ul{{margin:0;padding-left:18px}}.summary li{{overflow-wrap:anywhere}}.empty{{color:var(--muted);margin:0}}
section h2{{font-size:20px;margin:28px 0 12px;text-transform:capitalize}}section h2 small{{color:var(--muted);font-weight:400}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}}
.profile{{display:flex;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;min-width:0}}
.profile img,.no-avatar{{width:56px;height:56px;border-radius:8px;object-fit:cover;flex:none;background:var(--line)}}
.body{{min-width:0;flex:1}}.profile header{{display:flex;justify-content:space-between;gap:8px;align-items:baseline}}
.profile h3{{margin:0;font-size:16px}}.conf{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;font-weight:600}}
.c-high .conf{{color:var(--high)}}.c-medium .conf{{color:var(--medium)}}.c-low .conf{{color:var(--low)}}
a{{color:var(--accent)}}.url{{display:block;font-size:13px;overflow-wrap:anywhere}}.bio{{margin:6px 0;font-size:14px}}
dl{{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:6px 0 0;font-size:13px}}dt{{color:var(--muted)}}dd{{margin:0;overflow-wrap:anywhere}}
.links{{display:flex;flex-direction:column;font-size:12px;margin-top:4px}}.links a{{overflow-wrap:anywhere}}
footer{{margin-top:40px;color:var(--muted);font-size:13px}}
</style></head><body><main>
<h1>Dossier: {e(d.target)}</h1>
<p class="meta">{len(d.profiles)} public profiles · {d.checks} checks in {d.duration_s}s · {when}
{"· usernames tried: " + e(", ".join(d.usernames_tried)) if len(d.usernames_tried) > 1 else ""}</p>
<div class="summary">
<div><h2>Names</h2>{bullet_list(d.names()[:6])}</div>
<div><h2>Locations</h2>{bullet_list(d.locations()[:6])}</div>
<div><h2>Linked accounts</h2>{bullet_list(accounts)}</div>
<div><h2>Links</h2>{bullet_list(d.links()[:8], link=True)}</div>
</div>
{sections or '<p class="empty">No profiles found.</p>'}
<footer>Generated by Caramelo from public data. Medium/low confidence: the username exists, but it may belong to someone else.
Site list: WhatsMyName (CC BY-SA 4.0).</footer>
</main></body></html>"""

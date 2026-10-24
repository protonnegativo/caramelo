"""Regressions for problems found in review: hostile text, broken site rules, empty targets, stale caches."""
import asyncio
import io
import json

import httpx
import pytest
from rich.console import Console

from caramelo import Dossier, Profile, engine, sites
from caramelo.cli import main
from caramelo.engine import investigate_async
from caramelo.report import to_terminal


def run(coro):
    return asyncio.run(coro)


def test_markup_in_profile_text_does_not_break_the_report():
    d = Dossier(target="x[/]y", usernames_tried=["x"])
    d.profiles = [Profile(site="S[/]", url="https://e.example/x", username="x", name="[/bold] me", location="[red]",
                          bio="see [link=https://x]this[/link] and [/]", category="[b]social")]
    out = io.StringIO()
    to_terminal(d, Console(file=out, width=140, color_system=None))
    assert "[/bold] me" in out.getvalue()


def test_one_broken_site_does_not_end_the_search(monkeypatch):
    real = engine.fetch

    async def flaky(client, site, account, timeout):
        if site.name == "GitHub (User)":
            raise RuntimeError("weird site")
        return await real(client, site, account, timeout)

    monkeypatch.setattr(engine, "fetch", flaky)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(404, text="nope")))
    d = run(investigate_async("jane", sites={"GitHub (User)", "GitLab"}, pivot=False, client=client))
    assert "GitHub (User) (jane)" in d.no_response


@pytest.mark.parametrize("target", ["", "   ", "@", " @ "])
def test_empty_target_is_rejected(target):
    with pytest.raises(ValueError):
        run(investigate_async(target, sites={"GitHub (User)"}, pivot=False))


def test_cli_rejects_empty_username(capsys):
    assert main(["@", "--no-banner"]) == 2


def _write_cache(tmp_path, generated):
    cache = tmp_path / "caramelo"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "sites.json").write_text(json.dumps({"generated": generated, "sites": []}), encoding="utf-8")


def test_newer_update_cache_is_used(tmp_path, monkeypatch):
    monkeypatch.setenv("CARAMELO_CACHE", str(tmp_path))
    _write_cache(tmp_path, "9999-01-01T00:00:00+00:00")
    assert sites.list_info()["sites"] == 0


def test_older_update_cache_loses_to_a_newer_bundled_list(tmp_path, monkeypatch):
    monkeypatch.setenv("CARAMELO_CACHE", str(tmp_path))
    _write_cache(tmp_path, "2000-01-01T00:00:00+00:00")
    assert sites.list_info()["sites"] > 1000

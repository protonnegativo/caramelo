# 🐕 CARAMELO

<p align="center">
  <img src="docs/banner.png" alt="Caramelo startup banner: a braille portrait of a caramelo dog inside a target-lock HUD" width="760">
</p>

**C**ross-platform **A**ccount **R**econ **A**nd **M**apping **E**ngine for **L**ocating **O**nline-identities

*The Brazilian street dog that sniffs out everything.*

Passive username OSINT: give it a username (or a real name) and it finds the **public profiles** on 600+ sites, then builds a dossier with each profile's name, bio, avatar, location, creation date and links. **No API keys required.**

```bash
caramelo johndoe
caramelo "Maria Souza"
caramelo johndoe --html dossier.html
caramelo johndoe --json > dossier.json
```

## Install

```bash
pip install git+https://github.com/protonnegativo/caramelo
```

Requires Python 3.10+.

## How it works

1. **Checks the username on every site** in the [WhatsMyName](https://github.com/WebBreacher/WhatsMyName) list. Each site has a rule that confirms the profile from the response content: a page that merely loads is not enough, the profile has to exist.
2. **Extracts details from that same response**, with no extra request:
   - GitHub, GitLab, Codeberg, Keybase, Mastodon, Bluesky, Gravatar, dev.to, Docker Hub, Chess.com, Hacker News and Duolingo have dedicated extractors that read the public API's JSON.
   - Every other site goes through the page's meta tags (title, description, image).
3. **Follows the trail.** When a profile mentions another account (the Twitter handle on GitHub, Keybase proofs, Gravatar accounts), that username is checked too. Use `--no-pivot` to turn this off.
4. **Turns names into usernames.** For `"Maria Souza"` it tries `mariasouza`, `maria.souza`, `msouza` and so on. Those results get **low confidence**, or **medium** when the name on the profile matches, because the username may belong to someone else.

"Passive" means the person being searched is never contacted or notified. The sites being checked do see your IP address, as with any visit.

## As a library

```python
from caramelo import investigate

dossier = investigate("johndoe")
for p in dossier.profiles:
    print(p.site, p.url, p.name, p.confidence)

dossier.names()            # display names, most frequent first
dossier.linked_accounts()  # {"twitter": {"johndoe"}, ...}
dossier.to_json()          # everything as JSON
```

Inside async code (FastAPI, bots, Jupyter), use `await investigate_async(...)`. It also accepts your own `httpx.AsyncClient`, for example to route through a proxy.

`investigate()` options:

| Option | Default | What it does |
|---|---|---|
| `categories` | all | e.g. `{"social", "coding"}` (see `caramelo --categories`) |
| `sites` | all | e.g. `{"GitHub (User)", "Reddit"}` |
| `pivot` | `True` | follow accounts mentioned on the profiles |
| `max_pivots` | `5` | how many new usernames to follow |
| `concurrency` | `50` | simultaneous checks |
| `timeout` | `15` | seconds per site |
| `progress` | — | `fn(done, total, profile_or_None)` |

The site list ships with the package. `caramelo --update` (or `update_sites()`) downloads the latest one to `~/.cache/caramelo`.

## Responsible use

Caramelo is meant for **auditing your own exposure**, **authorized** pentests and red team engagements, and legitimate investigations. That is why:

- It only reads what is public: no logins, breach data, phone numbers, home addresses or government IDs.
- Dating and adult sites are excluded from every search.
- Using it to expose, stalk or harass someone is not allowed and may be a crime where you live (stalking and harassment laws, GDPR, LGPD and similar).

## Limitations

- Instagram, Facebook, LinkedIn and TikTok block almost everything without a login. Usually you can tell the profile exists, but not read its content.
- Sites change: a rule may break and cause a false positive or negative. `caramelo --update` brings in the community's fixes.
- Some sites rate-limit repeated checks from the same IP. The GitHub API, for example, allows 60 requests per hour without a login.

## Development

```bash
pip install -e ".[dev]"
pytest                # offline tests
pytest -m network     # one test against the real GitHub API
```

## Credits and license

The banner portrait was made from ["Caramelo Sargento Rex"](https://commons.wikimedia.org/wiki/File:Caramelo_%E2%80%9CSargento_Rex%E2%80%9D.jpg) by A209 (CC0, Wikimedia Commons). Regenerate the README image with `python scripts/render_banner.py`.

Code under the MIT license. The site list (`src/caramelo/data/wmn-data.json`) comes from the [WhatsMyName](https://github.com/WebBreacher/WhatsMyName) project, © Micah Hoffman, under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

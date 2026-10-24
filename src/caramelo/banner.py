"""Startup banner: a target-lock HUD around a braille portrait of a caramelo dog.

The portrait was made from "Caramelo Sargento Rex" (CC0, Wikimedia Commons): background removed,
Floyd–Steinberg dithered into braille cells (2x4 dots each).
"""
from __future__ import annotations

from rich.console import Console
from rich.text import Text

DOG = [
    '        ⢀⣠⣤⣤⣤⣤⣤⣤⣤⣄⣀⣤⣀                           ',
    '      ⢀⣴⣿⣿⣿⠛⠛⠿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣶⣶⣶⣶⣶⣦⣤⣀⡀            ',
    '     ⣠⣿⣯⡟⠻⠿⠃⢀⣀⢀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢽⣿⣿⣿⣿⣿⣿⣦           ',
    '    ⣼⣿⣼⡟⠁  ⣠⡟⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⣿⣿⣿⣿⣷⢿⣿⣿⣿⣿⣿⣿⣷⡀         ',
    '   ⣼⡿⢻⠏   ⣸⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⡿⡿⠿⡢ ⢿⣿⣿⣿⣿⣿⣿⣿⣽⡇⣿⣿⣷         ',
    '  ⣼⢟⠊⡀  ⢀⣾⣟⢿⣺⣿⣿⣿⣿⣿⣿⣿⣍⠙⠊  ⣾⢛⢹⣿⢯⣿⣿⣿⣿⣿⣿⡕⣵⡿⡆        ',
    ' ⣼⠯⠓    ⠈⣷⡿⣿⣿⣻⣿⣽⣾⣿⣿⣷⣿⣟⡲⣶⡿⡻⡳⡺⡧⣫⢺⡺⣿⣿⣿⣿⣿⣿⣽⡇        ',
    ' ⠛⠒⠃⠈⠈  ⠸⣻⡇⣻⣿⣿⣿⣿⣯⣿⣟⣞⠿⣽⡯⡿⡹⡮⣻⣝⡞⡯⡯⡯⣫⢻⡿⣿⣿⣿⣿⣇        ',
    '        ⣰⣿⢹⡿⣿⣿⣟⣿⣿⣿⡿⣿⣿⣣⢕⡽⣷⢽⣷⢟⢕⢯⢯⢺⢸⢕⣯⣾⣻⣿⣿⣿⣿⣦⣄⡀    ',
    '       ⢰⣿⡿⣾⣿⣿⣿⣾⣻⣽⣿⣻⡵⣻⣷⣿⢿⣯⡾⠓⠢⣵⣵⣱⢕⢕⣷⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣄  ',
    '       ⣾⣿⣗⢿⣿⣿⣽⡿⣵⣯⣾⣿⣯⣯⣿⣿⣯⣭⣅  ⠈⠙⠿⣞⠜⠬⡱⡙⣫⣟⣿⣿⠿⠛⠋⠛⠛⠙  ',
    '     ⢀⣼⣿⣿⣧⠻⣿⣿⢾⠯⣿⣿⣿⡩⠙⠱⠼⣏⡹⣞⠫⡛⡒⣀⠢⡨⢊⠌⠍⡝⡲⡾⡻⡿⡀ ⣀⣄     ',
    '    ⢠⣾⣿⣿⣿⣧⢱⢹⣻⣝⢟⣎⢻⣿⣁ ⠐⠩⣪⣶⣬⡱⣥⢕⠡⡙⠕⠿⢦⢵⡖⣕⣕⣽⠧⡑⡀⠈⠁     ',
    '   ⣀⣿⣿⣿⣿⣿⣿⡜⣜⢎⣾⡿⣼⣟⢼⡻⣦⠠⡟⢿⣿⣷⣅⠚⢤⣅⠨⠑⠈⠒⢹⡿⣬⣫⣫⠻⡦⣣⡄⡀     ',
    '⣿⣿⣿⣿⣿⣿⣿⣿⣗⢿⣷⢱⣕⢝⢟⢵⢗⣵⢹⢿⣧⠹⣿⠻⡽⣿⣷⣠⡀    ⠈⠻⢺⢑⣯⡷⠽⣓⠲⠇     ',
    '⣿⣿⣿⡿⣿⣿⣿⣿⡽⡵⡽⣧⣿⢜⢆⢇⣇⢊⢌⢒⣍⣷⣄⡉⣹⣦⣽⣻⣷⣶⡴⣄⡀    ⠈⢳⣦⡀       ',
    '⣿⣿⣿⡯⡯⣿⣿⣯⡿⣯⣿⣿⣞⢷⡱⢕⢇⢧⢂⢹⣿⣿⣻⣿⣮⡫⣝⣷⢻⣻⣟⣿⣿⣷⣤⣤⢠⡀⣻⠿⣷⡀      ',
    '⣿⣿⣿⣿⣿⡝⡜⣿⣿⣿⣷⣿⣿⣷⣻⡎⡎⡝⡄⢽⣝⣟⣟⣿⣿⣿⣦⡰⣻⣿⣿⣿⣾⣕⢿⣿⣒⢿⣃⢣⢻⣷      ',
    '⣿⡿⣷⣿⣿⣵⢱⠨⡋⡻⣿⣷⣿⢿⡗⡝⢎⢎⢕⢽⣿⣾⣿⣿⣿⣿⣿⠟⠛⠽⣛⣾⣷⣟⡽⣪⢎⢞⢏⢆⢕⢿      ',
    '⣿⣿⣿⣿⣿⣿⣷⢅⠕⠠⠈⠻⣿⣿⢿⣎⢦⢇⢣⡛⣿⣿⣿⣿⣿⣿⡟    ⠙⠛⢯⢯⡳⣕⡵⠵⠬⠦⠧⠃     ',
    '⣿⣿⣿⣿⣿⣿⣿⣷⣊⢈⠈ ⠈⢻⣿⣳⡽⡾⡸⣜⣿⣿⣿⣿⣟⡿⠁       ⠫⠗⠁           ',
    '⣿⣿⣿⣿⣿⣿⣿⣾⣿⣧⡐   ⠙⢿⣯⣗⡵⣻⣻⣿⣿⣷⡿⠁                      ',
    '⣿⢯⣿⣿⣟⣿⣾⣿⣿⣿⣿⣦⡀   ⠈⠙⢿⣗⡿⣽⣿⡟                        ',
    '⣿⣻⣿⣻⡿⣽⣻⣾⣿⣿⣽⣟⣿⣦⡀    ⠻⣿⣷⣿⣷⣤⡄                      ',
]

NAME = [
    '▄█▄    ██   █▄▄▄▄ ██   █▀▄▀█ ▄███▄   █    ████▄ ',
    '█▀ ▀▄  █ █  █  ▄▀ █ █  █ █ █ █▀   ▀  █    █   █ ',
    '█   ▀  █▄▄█ █▀▀▌  █▄▄█ █ ▄ █ ██▄▄    █    █   █ ',
    '█▄  ▄▀ █  █ █  █  █  █ █   █ █▄   ▄▀ ███▄ ▀████ ',
    '▀███▀     █   █      █    █  ▀███▀       ▀      ',
    '         █   ▀      █    ▀                      ',
    '        ▀          ▀                            ',
]

ACRONYM = "Cross-platform Account Recon And Mapping Engine for Locating Online-identities"
MOTTO = "The Brazilian street dog that sniffs out everything."

_FRAME = "bold #ffb000"
_AMBER, _ORANGE = (255, 176, 0), (255, 90, 0)
_HUD_WIDTH = 46
_GAP = "   "


def _mix(a, b, t):
    r, g, bl = (int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return f"#{r:02x}{g:02x}{bl:02x}"


def _portrait() -> list[Text]:
    """The dog inside the target-lock frame."""
    w = len(DOG[0])
    lines = [Text("┏━━" + " " * (w - 4) + "━━┓", style=_FRAME)]
    mid = len(DOG) // 2
    for i, row in enumerate(DOG):
        side = "╋" if i == mid else "┃" if i < 2 or i > len(DOG) - 3 else " "
        line = Text(side, style=_FRAME)
        line.append(row, style=_mix(_AMBER, _ORANGE, i / len(DOG)))
        line.append(side, style=_FRAME)
        lines.append(line)
    lines.append(Text("┗━━" + " " * (w - 4) + "━━┛", style=_FRAME))
    lines.append(Text(" TGT-LOCK ▸ 0x" + "CARAMELO".encode().hex(), style="#ff5a00"))
    return lines


def _name() -> list[Text]:
    w = len(NAME[0])
    lines = []
    for row in NAME:
        line = Text()
        for x, ch in enumerate(row):
            line.append(ch, style=f"bold {_mix(_AMBER, _ORANGE, x / max(1, w - 1))}" if ch.strip() else None)
        lines.append(line)
    return lines


def _hud(sites: int | None, version: str | None) -> list[Text]:
    def row(text: str, style: str) -> Text:
        return Text("│ " + text.ljust(_HUD_WIDTH - 1) + "│", style=style)

    bar = "█" * 17 + "░" * 3
    reach = f"{sites} sites · 0 API keys" if sites else "thousands of sites · 0 API keys"
    return [
        Text("╭─ SUBJECT " + "─" * (_HUD_WIDTH - 10) + "╮", style="#ffb000"),
        row("ID ........ CARAMELO // vira-lata", "#ffcc66"),
        row("CLASS ..... street dog · BR · 100% passive", "#ffcc66"),
        row(f"SCENT ..... {bar} 85%", "#ff8a00"),
        row(f"RANGE ..... {reach}", "#ffcc66"),
        row(f"BUILD ..... v{version}" if version else "BUILD ..... dev", "#ffcc66"),
        Text("╰" + "─" * _HUD_WIDTH + "╯", style="#ffb000"),
    ]


def _side_by_side(left: list[Text], right: list[Text], top: int) -> list[Text]:
    width = max(len(t.plain) for t in left)
    out = []
    for i in range(max(len(left), len(right) + top)):
        line = Text()
        if i < len(left):
            line.append_text(left[i])
            line.append(" " * (width - len(left[i].plain)))
        else:
            line.append(" " * width)
        j = i - top
        if 0 <= j < len(right):
            line.append(_GAP)
            line.append_text(right[j])
        out.append(line)
    return out


def full_width() -> int:
    return len(DOG[0]) + 2 + len(_GAP) + _HUD_WIDTH + 2


def render(width: int = 120, sites: int | None = None, version: str | None = None) -> Text:
    """The banner as rich Text. Below `full_width()` columns the portrait is dropped."""
    right = _name() + [Text("")] + _hud(sites, version)
    text = Text()
    if width >= full_width():
        lines = _side_by_side(_portrait(), right, top=3)
    else:
        lines = right
    for line in lines:
        text.append_text(line)
        text.append("\n")
    if width >= len(ACRONYM):
        text.append(ACRONYM, style="dim #ffcc66").append("\n")
    text.append(MOTTO, style="italic #ff5a00").append("\n")
    return text


def show(console: Console, sites: int | None = None, version: str | None = None) -> None:
    console.print(render(console.width, sites, version), highlight=False, soft_wrap=True, crop=False)

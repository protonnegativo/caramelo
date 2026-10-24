"""Renders the CLI banner to docs/banner.png for the README (GitHub doesn't show terminal colors).

Dev-only: needs Pillow (`pip install pillow`) and a monospace font plus a font with braille glyphs.
Defaults are the Windows ones (Consolas + Segoe UI Symbol); pass other .ttf paths on other systems:

    python scripts/render_banner.py [MONO.ttf] [SYMBOLS.ttf]
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rich.console import Console

from caramelo import __version__, load_sites
from caramelo.banner import full_width, render

ROOT = Path(__file__).resolve().parents[1]
MONO = sys.argv[1] if len(sys.argv) > 1 else r"C:\Windows\Fonts\consola.ttf"
SYMBOLS = sys.argv[2] if len(sys.argv) > 2 else r"C:\Windows\Fonts\seguisym.ttf"
SIZE, CELL_W, CELL_H, PAD = 16, 9, 19, 24
BACKGROUND = (10, 10, 12)


def main() -> None:
    mono, symbols = ImageFont.truetype(MONO, SIZE), ImageFont.truetype(SYMBOLS, SIZE)
    width = full_width() + 2
    console = Console(width=width, force_terminal=True, color_system="truecolor", file=io.StringIO())
    text = render(width, sites=len(load_sites()), version=__version__)
    lines = console.render_lines(text, console.options.update(width=width), pad=False, new_lines=False)
    cols = max(sum(len(s.text) for s in line) for line in lines)

    img = Image.new("RGB", (cols * CELL_W + 2 * PAD, len(lines) * CELL_H + 2 * PAD), BACKGROUND)
    draw = ImageDraw.Draw(img)
    for y, line in enumerate(lines):
        x = 0
        for seg in line:
            color = seg.style.color.get_truecolor() if seg.style and seg.style.color else (220, 220, 220)
            for ch in seg.text:
                if ch.strip():
                    font = symbols if 0x2800 <= ord(ch) <= 0x28FF else mono
                    draw.text((PAD + x * CELL_W, PAD + y * CELL_H), ch, font=font, fill=tuple(color))
                x += 1
    out = ROOT / "docs" / "banner.png"
    out.parent.mkdir(exist_ok=True)
    img.save(out, optimize=True)
    print(f"saved {out} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()

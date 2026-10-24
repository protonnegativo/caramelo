"""Speeds up the waiting parts of a recorded GIF (e.g. docs/demo.gif from `vhs docs/demo.tape`).

Typing and output stay at real speed; only the given time ranges are fast-forwarded, and the last half second
of each range plays normally so the viewer sees it finish. Frames that don't change are merged.

    python scripts/speedup_gif.py IN.gif OUT.gif --wait 3.1-13.88:8 --wait 18.4-37.3:6 --wait 43.4-56.6:10 --hold-end 1.5

Each --wait is START-END:FACTOR in seconds of the original GIF. Needs Pillow and numpy (dev-only).
"""
from __future__ import annotations

import argparse

import numpy as np
from PIL import Image, ImageSequence

STEP_MS = 40          # output frame time inside sped-up ranges (GIF players clamp anything under 20 ms)
KEEP_NORMAL_S = 0.5   # tail of each wait that plays at real speed


def parse_wait(text: str) -> tuple[float, float, float]:
    span, factor = text.split(":")
    start, end = span.split("-")
    return float(start), float(end), float(factor)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--wait", action="append", type=parse_wait, default=[], metavar="START-END:FACTOR")
    p.add_argument("--hold-end", type=float, default=0.0, help="extra seconds on the last frame")
    a = p.parse_args()

    src = Image.open(a.src)
    frames, starts, t = [], [], 0
    for fr in ImageSequence.Iterator(src):
        rgb = fr.convert("RGB")
        rgb.info = {}  # drop the source's transparency/palette metadata; frames are re-encoded below
        frames.append(rgb)
        starts.append(t)
        t += fr.info.get("duration", STEP_MS)
    total_ms = t

    def frame_at(ms: float) -> Image.Image:
        i = max(0, np.searchsorted(starts, ms, side="right") - 1)
        return frames[i]

    # Build the output timeline: (frame, duration_ms)
    out: list[tuple[Image.Image, int]] = []
    waits = sorted((int(s * 1000), int((e - KEEP_NORMAL_S) * 1000), f) for s, e, f in a.wait)
    cursor = 0
    for w_start, w_end, factor in waits + [(total_ms, total_ms, 1)]:
        for i, s in enumerate(starts):  # real-speed frames before this wait
            if cursor <= s < w_start:
                end = starts[i + 1] if i + 1 < len(starts) else total_ms
                out.append((frames[i], min(end, w_start) - s))
        ms = w_start
        while ms < w_end:  # fast-forward: one output frame per STEP_MS * factor of source time
            out.append((frame_at(ms), STEP_MS))
            ms += STEP_MS * factor
        cursor = max(w_end, w_start)
        if cursor < total_ms:  # partial source frame where the wait ends
            i = max(0, np.searchsorted(starts, cursor, side="right") - 1)
            nxt = starts[i + 1] if i + 1 < len(starts) else total_ms
            if starts[i] < cursor:
                out.append((frames[i], nxt - cursor))
                cursor = nxt
    if a.hold_end and out:
        frame, dur = out[-1]
        out[-1] = (frame, dur + int(a.hold_end * 1000))

    # Merge identical consecutive frames.
    merged: list[list] = []
    last = None
    for frame, dur in out:
        if dur <= 0:
            continue
        raw = frame.tobytes()
        if raw == last:
            merged[-1][1] += dur
        else:
            merged.append([frame, dur])
            last = raw

    palette = max((f for f, _ in merged), key=lambda f: len(f.getcolors(1 << 20) or [])).quantize(colors=256)
    paletted = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f, _ in merged]
    for p_frame in paletted:
        p_frame.info = {}
    durations = [max(20, int(d)) for _, d in merged]
    paletted[0].save(a.dst, save_all=True, append_images=paletted[1:], duration=durations, loop=0,
                     optimize=True, disposal=1)
    print(f"{total_ms / 1000:.1f}s → {sum(durations) / 1000:.1f}s, {len(merged)} frames")


if __name__ == "__main__":
    main()

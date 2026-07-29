#!/usr/bin/env python3
"""Scene plan -> PNG stills, composited with Pillow from design tokens.

One PNG per scene, rendered slightly oversize so build_video.py can pan across
it. No browser, no Node: the capsule has Pillow and Noto CJK fonts already, and
a headless Chromium neither fits the disk nor survives the RAM.

Usage:
    python3 render_scenes.py plan.json -o scenes/ --contact-sheet contact.png
    python3 render_scenes.py plan.json -o scenes/ --only 3,7   # re-render two scenes

The design preset comes from the plan; --designs only matters if you keep the
token file somewhere other than the skill's own assets/ directory.
"""

import argparse
import json
import subprocess
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 1920x1080 is the delivery frame; render 6% larger so a pan has headroom and
# still never exposes an edge. Everything below is authored against REF.
REF_W, REF_H = 1920, 1080
HEADROOM = 0.06
CANVAS_W, CANVAS_H = int(REF_W * (1 + HEADROOM)), int(REF_H * (1 + HEADROOM))
PAN_X, PAN_Y = (CANVAS_W - REF_W) // 2, (CANVAS_H - REF_H) // 2
# Content must survive the pan at both extremes, so it lives in the intersection
# of every crop window, inset again for breathing room.
MARGIN = 104
SAFE = (PAN_X + MARGIN, PAN_Y + MARGIN, CANVAS_W - PAN_X - MARGIN, CANVAS_H - PAN_Y - MARGIN)

FONT_SPECS = {
    "black": "Noto Sans CJK SC:weight=210",
    "bold": "Noto Sans CJK SC:weight=200",
    "regular": "Noto Sans CJK SC:weight=80",
}


def hexrgb(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


@lru_cache(maxsize=None)
def _font_file(spec: str) -> tuple[str, int]:
    """Resolve a fontconfig pattern to (path, collection index).

    The index matters: Noto's CJK .ttc packs SC/TC/JP/KR in one file and index 0
    is not Simplified Chinese, so dropping it silently renders Japanese glyph
    variants for shared characters.
    """
    out = subprocess.run(
        ["fc-match", "-f", "%{file}\t%{index}", spec], capture_output=True, text=True
    ).stdout
    if "\t" not in out:
        sys.exit(f"error: fc-match found no font for {spec!r}")
    path, idx = out.split("\t", 1)
    return path.strip(), int(idx.strip() or 0)


@lru_cache(maxsize=None)
def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    path, idx = _font_file(FONT_SPECS[weight])
    return ImageFont.truetype(path, size, index=idx)


def _is_cjk(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in ("W", "F") or "一" <= ch <= "鿿"


def wrap(text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Wrap mixed CJK/Latin text: CJK breaks between characters, Latin at spaces."""
    if not text:
        return []
    lines: list[str] = []
    line = ""
    tokens: list[str] = []
    buf = ""
    for ch in text:
        if _is_cjk(ch):
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        elif ch == " ":
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(" ")
        else:
            buf += ch
    if buf:
        tokens.append(buf)

    for tok in tokens:
        trial = line + tok
        if f.getlength(trial.rstrip()) <= max_w or not line.strip():
            line = trial
        else:
            lines.append(line.rstrip())
            line = "" if tok == " " else tok
    if line.strip():
        lines.append(line.rstrip())
    return lines


def fit(text: str, weight: str, start: int, max_w: int, max_lines: int, floor: int = 30):
    """Largest size at which `text` wraps into at most `max_lines`."""
    size = start
    while size > floor:
        f = font(weight, size)
        ls = wrap(text, f, max_w)
        if len(ls) <= max_lines:
            return f, ls
        size -= 4
    f = font(weight, floor)
    return f, wrap(text, f, max_w)[:max_lines]


def track(d: ImageDraw.ImageDraw, xy, text, f, fill, tracking: float) -> None:
    """Draw letter-spaced text (Pillow has no tracking of its own)."""
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + f.size * tracking


def _shadowed_rect(d, box, fill, tk, outline=None) -> None:
    """Filled rect with the preset's hard offset shadow and ink border."""
    off = tk.get("hard_shadow", 0)
    r = tk.get("corner", 0)
    if off:
        d.rounded_rectangle([box[0] + off, box[1] + off, box[2] + off, box[3] + off],
                            radius=r, fill=hexrgb(tk["ink"]))
    d.rounded_rectangle(box, radius=r, fill=fill,
                        outline=outline, width=tk.get("border_width", 0) or 0)


# --------------------------------------------------------------------------
# layouts — composed as a stack of blocks, then placed as one unit
# --------------------------------------------------------------------------
#
# Every layout builds a list of blocks and hands it to `place`, which measures
# the whole stack and centres it. Doing the arithmetic per layout is how frames
# end up hugging the top with dead space underneath: the centring has to account
# for the kicker and the body, not just the headline.


def block(lines, f, fill, lead=1.14, gap=0, tracking=0.0) -> dict:
    return {"lines": lines, "font": f, "fill": fill, "lead": lead,
            "gap": gap, "tracking": tracking}


def stack_height(blocks: list[dict]) -> int:
    return sum(b["gap"] + len(b["lines"]) * int(b["font"].size * b["lead"]) for b in blocks)


def place(d, blocks: list[dict], x: int, top: int, bottom: int, shift: int = 0) -> None:
    """Draw a block stack vertically centred between `top` and `bottom`."""
    y = top + max(0, (bottom - top - stack_height(blocks)) // 2) + shift
    for b in blocks:
        y += b["gap"]
        for ln in b["lines"]:
            if b["tracking"]:
                track(d, (x, y), ln, b["font"], b["fill"], b["tracking"])
            else:
                d.text((x, y), ln, font=b["font"], fill=b["fill"])
            y += int(b["font"].size * b["lead"])


def kicker_block(sc, tk, colour=None) -> list[dict]:
    text = (sc.get("kicker") or "").strip()
    if not text:
        return []
    if tk.get("kicker_case") == "upper":
        text = text.upper()
    return [block([text], font("bold", 38), colour or hexrgb(tk["accent"]),
                  lead=1.9, tracking=tk.get("kicker_tracking", 0.2))]


def layout_title(d, sc, tk) -> None:
    x0, y0, x1, y1 = SAFE
    w = x1 - x0
    fh, hl = fit(sc.get("headline", ""), "black", 168, w, 3)
    blocks = kicker_block(sc, tk) + [block(hl, fh, hexrgb(tk["ink"]), lead=1.12)]
    if (sc.get("body") or "").strip():
        fb, bl = fit(sc["body"], "regular", 52, w, 2)
        blocks.append(block(bl, fb, hexrgb(tk["muted"]), lead=1.42, gap=int(fh.size * 0.3)))
    place(d, blocks, x0, y0, y1)


def layout_statement(d, sc, tk) -> None:
    x0, y0, x1, y1 = SAFE
    w = x1 - x0
    fh, hl = fit(sc.get("headline", ""), "black", 132, w, 4)
    blocks = kicker_block(sc, tk) + [block(hl, fh, hexrgb(tk["ink"]), lead=1.14)]
    if (sc.get("body") or "").strip():
        fb, bl = fit(sc["body"], "regular", 50, w, 3)
        blocks.append(block(bl, fb, hexrgb(tk["muted"]), lead=1.44, gap=int(fh.size * 0.32)))
    place(d, blocks, x0, y0, y1)


def layout_bullets(d, sc, tk) -> None:
    """Headline on top, items spread through the space that is left."""
    x0, y0, x1, y1 = SAFE
    items = [str(i) for i in (sc.get("bullets") or [])][:6]
    fh, hl = fit(sc.get("headline", ""), "black", 104, x1 - x0, 2)
    head = kicker_block(sc, tk) + [block(hl, fh, hexrgb(tk["ink"]), lead=1.14)]
    place(d, head, x0, y0, y0 + stack_height(head))

    top = y0 + stack_height(head)
    size = 62 if len(items) <= 3 else (54 if len(items) <= 4 else 46)
    fi, fn = font("regular", size), font("bold", size)
    num_w = int(fn.getlength("00")) + 36
    # Measure everything first, then spread the leftover height over n+1 gaps —
    # one above the first item too, or the list crowds the headline while the
    # items drift apart from each other.
    wrapped = [wrap(it, fi, x1 - x0 - num_w)[:2] for it in items]
    used = sum(len(w) * int(fi.size * 1.26) for w in wrapped)
    gap = max(int(fi.size * 0.5), (max(0, (y1 - top) - used)) // (len(wrapped) + 1))
    y = top + gap
    for i, lines in enumerate(wrapped, 1):
        d.text((x0, y), f"{i:02d}", font=fn, fill=hexrgb(tk["accent"]))
        for ln in lines:
            d.text((x0 + num_w, y), ln, font=fi, fill=hexrgb(tk["ink"]))
            y += int(fi.size * 1.26)
        y += gap


def layout_stat(d, sc, tk) -> None:
    x0, y0, x1, y1 = SAFE
    stat = sc.get("stat") or {}
    value = str(stat.get("value", sc.get("headline", "")))
    label = str(stat.get("label", sc.get("body", "")))
    fv, vl = fit(value, "black", 400, x1 - x0, 1, floor=120)
    blocks = kicker_block(sc, tk) + [block(vl, fv, hexrgb(tk["accent"]), lead=1.06)]
    if label.strip():
        fl, ll = fit(label, "regular", 58, x1 - x0, 3)
        blocks.append(block(ll, fl, hexrgb(tk["ink"]), lead=1.4, gap=48))
    place(d, blocks, x0, y0, y1)


def layout_quote(d, sc, tk) -> None:
    x0, y0, x1, y1 = SAFE
    indent = 72
    fq, ql = fit(sc.get("headline", ""), "bold", 96, x1 - x0 - indent, 5)
    blocks = [block(ql, fq, hexrgb(tk["ink"]), lead=1.3)]
    if (sc.get("body") or "").strip():
        blocks.append(block([f"— {sc['body'].strip()}"], font("regular", 46),
                            hexrgb(tk["muted"]), lead=1.4, gap=40))
    top = y0 + max(0, (y1 - y0 - stack_height(blocks)) // 2)
    d.rectangle([x0, top, x0 + tk.get("rule_width", 5), top + len(ql) * int(fq.size * 1.3)],
                fill=hexrgb(tk["accent"]))
    place(d, blocks, x0 + indent, y0, y1)


def layout_chapter(d, sc, tk) -> None:
    """Full-bleed accent card — a hard beat between sections."""
    x0, y0, x1, y1 = SAFE
    d.rectangle([0, 0, CANVAS_W, CANVAS_H], fill=hexrgb(tk["accent"]))
    ink = hexrgb(tk["accent_ink"])
    blocks = []
    num = (sc.get("kicker") or "").strip()
    if num:
        blocks.append(block([num], font("black", 260), ink, lead=1.05))
    fh, hl = fit(sc.get("headline", ""), "black", 140, x1 - x0, 3)
    blocks.append(block(hl, fh, ink, lead=1.12, gap=30 if num else 0))
    place(d, blocks, x0, y0, y1)


def layout_outro(d, sc, tk) -> None:
    x0, y0, x1, y1 = SAFE
    fh, hl = fit(sc.get("headline", ""), "black", 150, x1 - x0, 3)
    blocks = kicker_block(sc, tk) + [block(hl, fh, hexrgb(tk["ink"]), lead=1.14)]
    if (sc.get("body") or "").strip():
        fb, bl = fit(sc["body"], "regular", 52, x1 - x0, 2)
        blocks.append(block(bl, fb, hexrgb(tk["muted"]), lead=1.42, gap=int(fh.size * 0.3)))
    place(d, blocks, x0, y0, y1)


LAYOUTS = {
    "title": layout_title,
    "statement": layout_statement,
    "bullets": layout_bullets,
    "stat": layout_stat,
    "quote": layout_quote,
    "chapter": layout_chapter,
    "outro": layout_outro,
}


def chrome(d, tk, progress: float) -> None:
    """Persistent furniture: a hairline frame and a progress bar. Nothing else.

    Restraint is the point — per-frame labels ('16:9', a tagline) are noise that
    sits on every single frame of the finished video.
    """
    bw = tk.get("border_width", 0)
    if bw:
        inset = PAN_X + 34
        d.rectangle(
            [inset, PAN_Y + 34, CANVAS_W - inset, CANVAS_H - PAN_Y - 34],
            outline=hexrgb(tk["ink"]),
            width=max(2, bw),
        )
    h = max(6, tk.get("rule_width", 5))
    d.rectangle([0, CANVAS_H - h, int(CANVAS_W * progress), CANVAS_H], fill=hexrgb(tk["accent"]))


def render(scene: dict, tk: dict, progress: float) -> Image.Image:
    im = Image.new("RGB", (CANVAS_W, CANVAS_H), hexrgb(tk["bg"]))
    d = ImageDraw.Draw(im)
    kind = scene.get("layout", "statement")
    if kind not in LAYOUTS:
        sys.exit(f"error: scene {scene.get('index')} has unknown layout {kind!r}; "
                 f"pick one of {', '.join(sorted(LAYOUTS))}")
    LAYOUTS[kind](d, scene, tk)
    if kind != "chapter":
        chrome(d, tk, progress)
    return im


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Render scene stills from a plan.")
    ap.add_argument("plan")
    ap.add_argument("--designs", default=str(here.parent / "assets" / "designs.json"))
    ap.add_argument("-o", "--output", default="scenes")
    ap.add_argument("--only", default="", help="Comma-separated scene indices to re-render")
    ap.add_argument("--contact-sheet", default="", help="Also write a grid of every scene")
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    designs = json.loads(Path(args.designs).read_text(encoding="utf-8"))
    name = plan.get("design", "blockframe")
    if name not in designs:
        known = ", ".join(k for k in designs if not k.startswith("_"))
        sys.exit(f"error: unknown design {name!r}; have {known}")
    tk = designs[name]

    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)
    only = {int(x) for x in args.only.split(",") if x.strip()} if args.only.strip() else None

    scenes = plan["scenes"]
    total = plan.get("audio_duration") or sum(s["duration"] for s in scenes)
    written = []
    for sc in scenes:
        path = outdir / f"s{sc['index']:03d}.png"
        if only is None or sc["index"] in only:
            im = render(sc, tk, min(1.0, (sc["start"] + sc["duration"]) / total))
            im.save(path, optimize=True)
        written.append(path)
        print(f"  s{sc['index']:03d}  {sc.get('layout'):9s}  {path}")

    if args.contact_sheet:
        cols = 4
        rows = (len(written) + cols - 1) // cols
        tw, th = 480, 270
        sheet = Image.new("RGB", (cols * tw, rows * th), (24, 24, 26))
        dd = ImageDraw.Draw(sheet)
        badge = font("bold", 26)
        for i, p in enumerate(written):
            thumb = Image.open(p).resize((tw, th), Image.LANCZOS)
            x, y = (i % cols) * tw, (i // cols) * th
            sheet.paste(thumb, (x, y))
            # Bottom-right: scene copy starts top-left, so a badge there would
            # cover the very thing the sheet exists to show.
            dd.rectangle([x + tw - 62, y + th - 44, x + tw - 8, y + th - 8], fill=(0, 0, 0))
            dd.text((x + tw - 52, y + th - 40), f"{i + 1:02d}", font=badge, fill=(255, 255, 255))
        sheet.save(args.contact_sheet)
        print(f"contact sheet -> {args.contact_sheet}")

    print(f"\n{len(written)} scenes at {CANVAS_W}x{CANVAS_H} (delivers {REF_W}x{REF_H})")


if __name__ == "__main__":
    main()

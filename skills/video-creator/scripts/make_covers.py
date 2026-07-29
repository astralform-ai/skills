#!/usr/bin/env python3
"""One cover, five aspect ratios, same design tokens as the video.

Covers are re-laid out per ratio, never letterboxed or cropped from a single
master — a 16:9 title squeezed into 9:16 is what makes a thumbnail look cheap.

Usage:
    python3 make_covers.py --title "标题" --subtitle "..." -o covers/
    python3 make_covers.py --title "..." --points "A,B,C" --design midnight
    python3 make_covers.py --from-plan plan.json          # title from scene 1
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from render_scenes import fit, font, hexrgb, track, wrap

# label -> (width, height). Portrait ratios get their own layout weighting.
RATIOS = {
    "16x9": (1920, 1080),
    "16x10": (1920, 1200),
    "4x3": (1440, 1080),
    "3x4": (1080, 1440),
    "9x16": (1080, 1920),
}


def cover(size: tuple[int, int], tk: dict, args) -> Image.Image:
    """Lay the cover out for this ratio, measuring before placing anything.

    Starting at a fixed fraction of the height is what leaves a 9:16 cover with
    its content jammed into the top third: the block has to be measured, then
    centred in the space the brand pill does not use.
    """
    w, h = size
    portrait = h > w
    im = Image.new("RGB", (w, h), hexrgb(tk["bg"]))
    d = ImageDraw.Draw(im)

    margin = int(min(w, h) * 0.085)
    box_w = w - margin * 2
    # Scale type off the short edge so portrait covers stay legible as thumbnails.
    unit = min(w, h)

    ink, accent, muted = hexrgb(tk["ink"]), hexrgb(tk["accent"]), hexrgb(tk["muted"])
    rule_h = max(4, int(unit * 0.007)) if tk.get("hard_shadow") else 0

    # --- measure -----------------------------------------------------------
    parts: list[tuple] = []  # (kind, font, lines, colour, gap_before, line_h)
    if (args.kicker or "").strip():
        fk = font("bold", int(unit * 0.026))
        parts.append(("kicker", fk, [args.kicker.strip().upper()], accent, 0,
                      int(fk.size * 1.9)))

    ft, tlines = fit(args.title, "black", int(unit * (0.115 if not portrait else 0.098)),
                     box_w, 4 if portrait else 3)
    parts.append(("title", ft, tlines, ink, rule_h + int(unit * 0.02) if rule_h else 0,
                  int(ft.size * 1.12)))

    if args.subtitle:
        fs, slines = fit(args.subtitle, "regular", int(unit * 0.036), box_w, 3)
        parts.append(("sub", fs, slines, muted, int(unit * 0.028), int(fs.size * 1.4)))

    points = [p.strip() for p in (args.points or "").split(",") if p.strip()][:4]
    fp = fn = None
    if points:
        fp, fn = font("regular", int(unit * 0.032)), font("bold", int(unit * 0.032))
        parts.append(("points", fp, points, ink, int(unit * 0.05), int(fp.size * 1.62)))

    total = sum(gap + len(lines) * lh for _, _, lines, _, gap, lh in parts)
    # Leave the bottom band to the brand pill so the stack never collides with it.
    bottom = h - margin - int(unit * (0.10 if args.brand else 0.04))
    y = margin + max(0, (bottom - margin - total) // 2)

    # --- draw --------------------------------------------------------------
    for kind, f, lines, colour, gap, lh in parts:
        if kind == "title" and rule_h:
            # The poster rule belongs to the title, so it is drawn where the
            # title actually landed rather than at a guessed height.
            d.rectangle([margin, y + gap - rule_h - int(unit * 0.012),
                         w - margin, y + gap - int(unit * 0.012)], fill=ink)
        y += gap
        if kind == "kicker":
            track(d, (margin, y), lines[0], f, colour, tk.get("kicker_tracking", 0.2))
            y += lh
        elif kind == "points":
            for i, p in enumerate(lines, 1):
                d.text((margin, y), f"{i:02d}", font=fn, fill=accent)
                ind = margin + int(fn.getlength("00")) + int(unit * 0.028)
                for ln in wrap(p, f, w - margin - ind)[:1]:
                    d.text((ind, y), ln, font=f, fill=colour)
                y += lh
        else:
            for ln in lines:
                d.text((margin, y), ln, font=f, fill=colour)
                y += lh

    # Small brand pill, bottom-left. The only chrome a cover gets.
    if args.brand:
        fb = font("bold", int(unit * 0.026))
        pad = int(unit * 0.018)
        tw = fb.getlength(args.brand)
        px, py = margin, h - margin - int(unit * 0.062)
        d.rounded_rectangle([px, py, px + tw + pad * 2, py + fb.size + pad * 2],
                            radius=int(unit * 0.014), fill=accent)
        d.text((px + pad, py + pad), args.brand, font=fb, fill=hexrgb(tk["accent_ink"]))

    bar = max(6, int(unit * 0.008))
    d.rectangle([0, h - bar, w, h], fill=accent)
    return im


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Render the five-ratio cover set.")
    ap.add_argument("--title", default="")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--kicker", default="")
    ap.add_argument("--points", default="", help="Comma-separated, max 4")
    ap.add_argument("--brand", default="")
    ap.add_argument("--design", default="")
    ap.add_argument("--from-plan", default="")
    ap.add_argument("--designs", default=str(here.parent / "assets" / "designs.json"))
    ap.add_argument("--ratios", default=",".join(RATIOS))
    ap.add_argument("-o", "--output", default="covers")
    args = ap.parse_args()

    design = args.design
    if args.from_plan:
        plan = json.loads(Path(args.from_plan).read_text(encoding="utf-8"))
        design = design or plan.get("design", "blockframe")
        first = plan["scenes"][0]
        args.title = args.title or first.get("headline", "")
        args.subtitle = args.subtitle or first.get("body", "")
    design = design or "blockframe"

    if not args.title.strip():
        sys.exit("error: --title is required (or use --from-plan with a scene 1 headline)")

    designs = json.loads(Path(args.designs).read_text(encoding="utf-8"))
    if design not in designs:
        sys.exit(f"error: unknown design {design!r}")
    tk = designs[design]

    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)
    wanted = [r.strip() for r in args.ratios.split(",") if r.strip()]
    for label in wanted:
        if label not in RATIOS:
            sys.exit(f"error: unknown ratio {label!r}; have {', '.join(RATIOS)}")
        im = cover(RATIOS[label], tk, args)
        path = outdir / f"cover-{label}.png"
        im.save(path, optimize=True)
        print(f"  {label:6s} {RATIOS[label][0]}x{RATIOS[label][1]}  {path}")
    print(f"\n{len(wanted)} covers in {outdir}/")


if __name__ == "__main__":
    main()

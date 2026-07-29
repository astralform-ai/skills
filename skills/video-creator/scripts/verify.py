#!/usr/bin/env python3
"""Acceptance checks on the finished video — cheap, and they catch the real bugs.

Pulls one frame from the middle of every scene and checks three things that
otherwise only surface after upload:

* streams and duration agree with the narration;
* no two scenes render the identical frame (a duplicated or blank scene);
* no frame is a flat field of one colour (a scene that failed to draw).

Judging a dark design by average brightness gives false alarms, so blankness is
measured by how many distinct colours a frame actually has.

Usage:
    python3 verify.py renders/episode.mp4 --plan plan.json
    python3 verify.py renders/episode.mp4 --plan plan.json --sheet check.png
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


def probe(path: Path, entries: str) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    ).stdout.strip()


def grab(video: Path, t: float, dest: Path) -> bool:
    p = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video),
         "-frames:v", "1", str(dest)],
        capture_output=True, text=True,
    )
    return p.returncode == 0 and dest.exists()


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify the rendered video.")
    ap.add_argument("video")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--sheet", default="", help="Write a contact sheet of the sampled frames")
    args = ap.parse_args()

    video = Path(args.video)
    if not video.exists():
        sys.exit(f"error: {video} does not exist")
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))

    problems: list[str] = []

    # --- streams + duration -------------------------------------------------
    streams = probe(video, "stream=codec_type,codec_name,width,height")
    dur = float(probe(video, "format=duration") or 0)
    print(f"{video}  {dur:.2f}s")
    for line in streams.splitlines():
        print(f"  {line}")
    if "video" not in streams:
        problems.append("no video stream")
    if "audio" not in streams:
        problems.append("no audio stream — narration was not muxed")
    narr = float(plan.get("audio_duration") or 0)
    if narr:
        drift = dur - narr
        print(f"  narration {narr:.2f}s   drift {drift:+.2f}s")
        if abs(drift) > 1.5:
            problems.append(f"duration drifts {drift:+.1f}s from the narration")

    # --- one frame per scene ------------------------------------------------
    tmp = Path(tempfile.mkdtemp(prefix="verify-"))
    frames, seen = [], {}
    print("\nscene frames")
    for sc in plan["scenes"]:
        t = float(sc["start"]) + float(sc["duration"]) / 2
        if t >= dur:
            t = max(0.0, dur - 0.4)
        f = tmp / f"f{sc['index']:03d}.png"
        if not grab(video, t, f):
            problems.append(f"scene {sc['index']}: could not extract a frame at {t:.1f}s")
            continue
        digest = hashlib.md5(f.read_bytes()).hexdigest()
        im = Image.open(f).convert("RGB")
        colours = len(im.getcolors(maxcolors=1_000_000) or [])
        frames.append((sc["index"], f, colours))
        flag = ""
        if digest in seen:
            flag = f"  <-- IDENTICAL to scene {seen[digest]}"
            problems.append(f"scene {sc['index']} renders the same frame as scene {seen[digest]}")
        else:
            seen[digest] = sc["index"]
        if colours < 12:
            flag += "  <-- NEARLY BLANK"
            problems.append(f"scene {sc['index']} looks blank ({colours} distinct colours)")
        print(f"  {sc['index']:03d}  t={t:7.2f}s  {colours:6d} colours  {digest[:10]}{flag}")

    if args.sheet and frames:
        cols = 4
        rows = (len(frames) + cols - 1) // cols
        tw, th = 480, 270
        sheet = Image.new("RGB", (cols * tw, rows * th), (20, 20, 22))
        for i, (_, f, _) in enumerate(frames):
            sheet.paste(Image.open(f).resize((tw, th), Image.LANCZOS),
                        ((i % cols) * tw, (i // cols) * th))
        sheet.save(args.sheet)
        print(f"\ncontact sheet -> {args.sheet}")

    print()
    if problems:
        print(f"FAILED — {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print(f"PASSED — {len(frames)} scenes, all distinct, audio present, timing matches narration.")


if __name__ == "__main__":
    main()

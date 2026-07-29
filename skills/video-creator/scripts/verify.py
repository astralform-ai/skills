#!/usr/bin/env python3
"""Acceptance checks on the finished video — cheap, and they catch the real bugs.

Checks four things about the finished file that otherwise only surface after
upload:

* streams and duration agree with the narration;
* **each scene appears when the narration says it does** (with `--clips`) —
  computed exactly from the joined clip durations, not inferred from pixels;
* no two scenes render the same artwork (a duplicated or blank scene);
* no frame is a flat field of one colour (a scene that failed to draw).

Two traps this deliberately avoids:

* Total duration proves nothing on its own. The mux uses `-shortest`, so a video
  whose scenes have drifted late is silently truncated to the audio length and
  still reports the right total.
* Sampling each scene's midpoint proves little either: a scene has to drift by
  more than half its own length before the midpoint lands in the wrong one, so
  seconds of accumulated error pass unnoticed. The cut times are measured.
* Hashing the whole frame proves nothing either. The progress bar differs on
  every scene, so two scenes with identical artwork still hash differently. The
  chrome band is masked out before comparing.

Judging a dark design by average brightness gives false alarms, so blankness is
measured by how many distinct colours a frame actually has.

Usage:
    python3 verify.py renders/episode.mp4 --plan plan.json --clips clips/ --scenes scenes/
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

# The progress bar and frame border live in the outer band and vary per scene by
# design, so they are cropped away before any frame is compared to another.
CHROME_MARGIN = 0.055


def content_box(im: Image.Image) -> Image.Image:
    w, h = im.size
    dx, dy = int(w * CHROME_MARGIN), int(h * CHROME_MARGIN)
    return im.crop((dx, dy, w - dx, h - dy))


def signature(path: Path, size: int = 48) -> bytes:
    """A small, pan-tolerant fingerprint of a frame's artwork."""
    im = content_box(Image.open(path).convert("L")).resize((size, size), Image.LANCZOS)
    return im.tobytes()


def sig_distance(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def measure_starts(clips_dir: Path, plan: dict) -> tuple[dict[int, float], list[int]]:
    """When each scene actually appears, computed from the clips that were joined.

    The join is a stream copy, so a scene's on-screen start is exactly the sum of
    the durations of the clips before it — and `ffprobe` reports those durations
    exactly. Comparing that sum against the plan is the whole alignment check.

    An earlier version of this file tried to find each cut by matching frames
    against the scene stills. That is a hard computer-vision problem standing in
    for arithmetic, and it failed three different ways on correct video: the
    search window overran into a third scene, mid-fade frames resembled whichever
    card was closer in grey, and near-black frames matched a full-bleed card.
    Every one of those was a false alarm on a video that was fine.
    """
    starts: dict[int, float] = {}
    unmeasured: list[int] = []
    t = 0.0
    for sc in plan["scenes"]:
        i = sc["index"]
        clip = clips_dir / f"c{i:03d}.mp4"
        if not clip.exists():
            unmeasured.append(i)
            # Fall back to the plan so later scenes stay anchored; the caller
            # reports the gap rather than quietly trusting an unchecked cut.
            t = float(sc["start"]) + float(sc["duration"])
            continue
        starts[i] = t
        d = probe(clip, "format=duration")
        try:
            t += float(d)
        except ValueError:
            unmeasured.append(i)
            t = float(sc["start"]) + float(sc["duration"])
    return starts, unmeasured


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
    ap.add_argument("--scenes", default="",
                    help="Scene stills dir — enables the duplicate-artwork check")
    ap.add_argument("--clips", default="clips",
                    help="Per-scene clips dir — enables the alignment check")
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

    # --- reference signatures for the alignment check ------------------------
    scenes_dir = Path(args.scenes) if args.scenes else None
    refs: dict[int, bytes] = {}
    if scenes_dir:
        missing_stills = []
        for sc in plan["scenes"]:
            still = scenes_dir / f"s{sc['index']:03d}.png"
            if still.exists():
                refs[sc["index"]] = signature(still)
            else:
                missing_stills.append(sc["index"])
        if missing_stills:
            # A partial reference set silently skips the cuts it cannot judge,
            # so the run would still print PASSED while claiming every cut was
            # checked. Refuse to report alignment on an incomplete set.
            refs = {}
            problems.append(
                f"scene stills missing from {scenes_dir} for scenes {missing_stills} — "
                f"alignment cannot be checked; re-run render_scenes.py"
            )
    else:
        print("\nNOTE: no --scenes given, so scene alignment is NOT checked. "
              "Duration alone cannot detect drift; pass --scenes.")

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
        im = Image.open(f).convert("RGB")
        # Compare artwork only: the progress bar differs per scene by design and
        # would make two identical scenes look different.
        content = content_box(im)
        digest = hashlib.md5(content.tobytes()).hexdigest()
        colours = len(content.getcolors(maxcolors=1_000_000) or [])
        frames.append((sc["index"], f, colours))
        flag = ""

        if digest in seen:
            flag += f"  <-- SAME ARTWORK as scene {seen[digest]}"
            problems.append(f"scene {sc['index']} renders the same artwork as scene {seen[digest]}")
        else:
            seen[digest] = sc["index"]
        if colours < 12:
            flag += "  <-- NEARLY BLANK"
            problems.append(f"scene {sc['index']} looks blank ({colours} distinct colours)")
        print(f"  {sc['index']:03d}  t={t:7.2f}s  {colours:6d} colours  {digest[:10]}{flag}")

    # --- when does each scene actually appear? ------------------------------
    # Exact arithmetic, not image matching: the join is a stream copy, so a
    # scene's on-screen start is the sum of the preceding clip durations.
    clips_dir = Path(args.clips)
    if clips_dir.is_dir():
        tol = 0.35
        observed, unmeasured = measure_starts(clips_dir, plan)
        print("\nscene starts (narration vs picture)")
        worst = 0.0
        for sc in plan["scenes"]:
            i = sc["index"]
            if i not in observed:
                print(f"  {i:03d}  narration {float(sc['start']):7.2f}s      "
                      f"clip missing — NOT MEASURED")
                continue
            off = observed[i] - float(sc["start"])
            worst = max(worst, abs(off))
            mark = "  <-- DRIFTED" if abs(off) > tol else ""
            print(f"  {i:03d}  narration {float(sc['start']):7.2f}s   "
                  f"picture {observed[i]:7.2f}s   {off:+6.2f}s{mark}")
            if abs(off) > tol:
                problems.append(f"scene {i} appears {off:+.2f}s away from its narration cue")
        if unmeasured:
            problems.append(
                f"clips missing for scenes {unmeasured} — their cuts are unverified"
            )
        print(f"  worst |drift| {worst:.2f}s (tolerance {tol:.2f}s)")
    else:
        print(f"\nNOTE: {clips_dir}/ not found, so scene alignment is NOT checked. "
              f"Duration alone cannot detect drift; pass --clips.")
        problems.append(f"alignment unchecked — {clips_dir}/ not found")

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
    aligned = "cuts land on their cues, " if clips_dir.is_dir() else ""
    print(f"PASSED — {len(frames)} scenes, {aligned}all distinct, audio present.")


if __name__ == "__main__":
    main()

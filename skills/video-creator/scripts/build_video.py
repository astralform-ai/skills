#!/usr/bin/env python3
"""Scene stills + narration -> the finished MP4, in stages that fit the capsule.

Two capsule facts shape this script:

* `capsule_run_code` aborts a call at 300 s, so encoding runs in ranges you can
  spread over several calls (`--stage clips --from 1 --to 6`).
* `zoompan` exhausts the 2 GB box and the sandbox is killed, so motion is a crop
  window sliding across the render headroom — seconds per clip, flat memory.

Stages:
    clips   encode one MP4 per scene           (chunk this; the slow part)
    join    concatenate + mux narration        (fast: stream copy)
    all     clips + join                       (only for short videos)

Usage:
    python3 build_video.py plan.json --stage clips --from 1 --to 8
    python3 build_video.py plan.json --stage clips --from 9
    python3 build_video.py plan.json --stage join -o renders/episode.mp4
    python3 build_video.py plan.json --stage all --transition xfade   # short only
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REF_W, REF_H = 1920, 1080


def run(cmd: list[str], what: str) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"error: {what} failed (exit {p.returncode})\n{p.stderr[-2500:]}")


def probe(path: Path, entries: str) -> str:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
    )
    return p.stdout.strip()


def motion_filter(kind: str, dur: float, fps: int, fade: float) -> str:
    """A crop window sliding across the still's headroom for `dur` seconds."""
    p = f"min(t/{dur:.4f},1)"  # clamp: ffmpeg may evaluate t just past dur
    dx, dy = f"(in_w-{REF_W})", f"(in_h-{REF_H})"
    moves = {
        "pan-right": (f"{dx}*{p}", f"{dy}/2"),
        "pan-left": (f"{dx}*(1-{p})", f"{dy}/2"),
        "pan-down": (f"{dx}/2", f"{dy}*{p}"),
        "pan-up": (f"{dx}/2", f"{dy}*(1-{p})"),
        "still": (f"{dx}/2", f"{dy}/2"),
    }
    if kind not in moves:
        sys.exit(f"error: unknown motion {kind!r}; use one of {', '.join(moves)}")
    x, y = moves[kind]
    chain = (
        f"crop={REF_W}:{REF_H}:x='{x}':y='{y}',"
        f"scale={REF_W}:{REF_H},setsar=1,fps={fps}"
    )
    if fade > 0:
        # A short fade-in per clip reads as a deliberate scene change once the
        # clips are concatenated, and costs nothing — unlike a cross-fade, which
        # must re-encode every scene together.
        chain += f",fade=t=in:st=0:d={fade:.3f}"
    return chain + ",format=yuv420p"


def clip_path(work: Path, i: int) -> Path:
    return work / f"c{i:03d}.mp4"


def stage_clips(plan: dict, scenes_dir: Path, work: Path, lo: int, hi: int, fade: float) -> None:
    fps = int(plan.get("fps", 30))
    work.mkdir(parents=True, exist_ok=True)
    todo = [s for s in plan["scenes"] if lo <= s["index"] <= hi]
    if not todo:
        sys.exit(f"error: no scenes in range {lo}..{hi}")
    est = sum(float(s["duration"]) for s in todo) * 0.6
    print(f"encoding scenes {todo[0]['index']}..{todo[-1]['index']} "
          f"({len(todo)} clips, ~{est:.0f}s estimated)")
    if est > 260:
        print("  NOTE: estimate is near the 300 s capsule_run_code ceiling — "
              "split this range across two calls if it aborts.")
    for sc in todo:
        still = scenes_dir / f"s{sc['index']:03d}.png"
        if not still.exists():
            sys.exit(f"error: missing {still} — run render_scenes.py first")
        dur = float(sc["duration"])
        run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-loop", "1", "-t", f"{dur:.4f}", "-r", str(fps), "-i", str(still),
             "-vf", motion_filter(sc.get("motion", "still"), dur, fps, fade),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-pix_fmt", "yuv420p", str(clip_path(work, sc["index"]))],
            f"encoding scene {sc['index']}",
        )
        print(f"  clip {sc['index']:03d}  {dur:6.2f}s  {sc.get('motion', 'still')}")


def require_all_clips(plan: dict, work: Path) -> list[Path]:
    missing = [s["index"] for s in plan["scenes"] if not clip_path(work, s["index"]).exists()]
    if missing:
        sys.exit(f"error: clips not encoded yet for scenes {missing} — "
                 f"run --stage clips for those first")
    return [clip_path(work, s["index"]) for s in plan["scenes"]]


def join_concat(clips: list[Path], work: Path) -> Path:
    """Stream-copy concatenation — constant memory, effectively instant."""
    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    out = work / "joined.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(out)], "concatenating scenes")
    return out


def join_xfade(plan: dict, clips: list[Path], work: Path) -> Path:
    """True cross-wipes. Re-encodes the whole video — short pieces only.

    Offsets are the scenes' own start times: because each clip carries the
    transition's worth of overlap, the accumulated output timeline stays equal to
    the real one, so no drift accumulates down the chain.
    """
    tr = plan.get("transition", {}) or {}
    kind, d = tr.get("type", "wiperight"), float(tr.get("duration", 0.5))
    scenes = plan["scenes"]
    out = work / "joined.mp4"
    inputs: list[str] = []
    for c in clips:
        inputs += ["-i", str(c)]
    parts, prev = [], "[0:v]"
    for i in range(1, len(clips)):
        label = f"[v{i}]"
        parts.append(f"{prev}[{i}:v]xfade=transition={kind}:duration={d}"
                     f":offset={float(scenes[i]['start']):.4f}{label}")
        prev = label
    fc = (";".join(parts) + f";{prev}format=yuv420p[vout]") if parts \
        else "[0:v]format=yuv420p[vout]"
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc,
         "-map", "[vout]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", str(out)], "joining scenes with cross-wipes")
    return out


def mux(video: Path, audio: Path, out: Path, normalise: bool) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    # Video is copied, so the loudness pass costs seconds, not a re-render.
    af = "loudnorm=I=-14:TP=-1.5:LRA=11" if normalise else "anull"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio),
         "-map", "0:v", "-map", "1:a", "-af", af, "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], "muxing narration")


def report(plan: dict, out: Path) -> None:
    dur = float(probe(out, "format=duration") or 0)
    streams = probe(out, "stream=codec_type,codec_name,width,height")
    print(f"\n{out}  {dur:.2f}s  {out.stat().st_size / 1e6:.1f} MB")
    for line in streams.splitlines():
        print(f"  {line}")
    if "audio" not in streams:
        print("  WARNING: no audio stream — check the narration path in the plan")
    narr = float(plan.get("audio_duration") or 0)
    if narr and abs(dur - narr) > 1.5:
        print(f"  WARNING: video {dur:.1f}s vs narration {narr:.1f}s — "
              f"scene durations have drifted from the SRT")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the video from scene stills.")
    ap.add_argument("plan")
    ap.add_argument("--stage", choices=["clips", "join", "all"], default="all")
    ap.add_argument("--scenes", default="scenes")
    ap.add_argument("--work", default="clips", help="Where per-scene clips live between stages")
    ap.add_argument("-o", "--output", default="renders/episode.mp4")
    ap.add_argument("--from", dest="lo", type=int, default=1)
    ap.add_argument("--to", dest="hi", type=int, default=10**6)
    ap.add_argument("--transition", choices=["fade", "cut", "xfade"], default="fade")
    ap.add_argument("--fade", type=float, default=0.35, help="Per-clip fade-in seconds")
    ap.add_argument("--no-normalise", action="store_true", help="Skip the -14 LUFS pass")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("error: ffmpeg not installed — run scripts/bootstrap.sh first")

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    work = Path(args.work)

    if args.stage in ("clips", "all"):
        fade = args.fade if args.transition == "fade" else 0.0
        stage_clips(plan, Path(args.scenes), work, args.lo, args.hi, fade)

    if args.stage == "clips":
        done = sum(1 for s in plan["scenes"] if clip_path(work, s["index"]).exists())
        print(f"\n{done}/{len(plan['scenes'])} clips encoded. "
              f"Next: --stage clips for the rest, then --stage join")
        return

    audio = Path(plan["audio"])
    if not audio.exists():
        sys.exit(f"error: narration audio not found at {audio}")
    clips = require_all_clips(plan, work)

    print(f"joining {len(clips)} clips ({args.transition})")
    joined = join_xfade(plan, clips, work) if args.transition == "xfade" \
        else join_concat(clips, work)

    print("muxing narration" + ("" if args.no_normalise else " + loudnorm to -14 LUFS"))
    out = Path(args.output)
    mux(joined, audio, out, normalise=not args.no_normalise)
    report(plan, out)


if __name__ == "__main__":
    main()

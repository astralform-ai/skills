#!/usr/bin/env python3
"""SRT -> scene timeline. The narration is the clock; this script reads it.

Groups subtitle cues into scenes and computes each scene's start and duration
straight from the cue timestamps, so picture changes land on the words that
motivate them. Emits a plan skeleton you then fill with on-screen copy.

Usage:
    python3 srt_scenes.py narration.srt --audio narration.mp3 -o plan.json
    python3 srt_scenes.py narration.srt --audio narration.mp3 --target 30
    python3 srt_scenes.py narration.srt --audio narration.mp3 --breaks 1,7,14,22

Options:
    --audio PATH     Narration audio; its true duration ends the last scene.
    --target SEC     Aim for ~SEC-long scenes when auto-grouping (default 30).
    --breaks LIST    1-based cue indices that START a scene. Overrides --target
                     — use it once you have read the transcript and know where
                     the topic actually turns.
    --transition SEC Cross-fade length recorded in the plan (default 0.5). It is
                     NOT added to any scene's duration — build_video.py extends a
                     clip by it only when that clip is actually cross-faded.
    --design NAME    Design preset recorded in the plan (default blockframe).
    -o PATH          Output plan (default plan.json).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


def _secs(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def parse_srt(path: Path) -> list[dict]:
    """Parse an SRT into [{index, start, end, text}], tolerant of CRLF and BOM."""
    raw = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[dict] = []
    for block in re.split(r"\n{2,}", raw.strip()):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        stamp_at = next((i for i, ln in enumerate(lines) if TIME_RE.search(ln)), None)
        if stamp_at is None:
            continue
        m = TIME_RE.search(lines[stamp_at])
        text = " ".join(ln.strip() for ln in lines[stamp_at + 1 :]).strip()
        cues.append(
            {
                "index": len(cues) + 1,
                "start": _secs(*m.group(1, 2, 3, 4)),
                "end": _secs(*m.group(5, 6, 7, 8)),
                "text": text,
            }
        )
    if not cues:
        sys.exit(f"error: no cues parsed from {path} — is it really an SRT?")
    return cues


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
    )
    if out.returncode != 0 or not out.stdout.strip():
        sys.exit(f"error: ffprobe could not read {path} — run bootstrap.sh first?")
    return float(out.stdout.strip())


def group_by_target(cues: list[dict], target: float) -> list[int]:
    """Pick scene-start cue indices so scenes land near `target` seconds.

    Deliberately dumb: it only knows time, not meaning. Treat the result as a
    starting grid and re-cut with --breaks once you have read the transcript.
    """
    starts = [0]
    anchor = cues[0]["start"]
    for i, cue in enumerate(cues[1:], start=1):
        if cue["start"] - anchor >= target:
            starts.append(i)
            anchor = cue["start"]
    return starts


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a scene timeline from an SRT.")
    ap.add_argument("srt")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--target", type=float, default=30.0)
    ap.add_argument("--breaks", default="")
    ap.add_argument("--transition", type=float, default=0.5)
    ap.add_argument("--design", default="blockframe")
    ap.add_argument("-o", "--output", default="plan.json")
    args = ap.parse_args()

    cues = parse_srt(Path(args.srt))
    total = audio_duration(Path(args.audio))

    if args.breaks.strip():
        starts = sorted({int(x) - 1 for x in args.breaks.split(",") if x.strip()})
        if starts and starts[0] != 0:
            starts.insert(0, 0)
        bad = [s for s in starts if not 0 <= s < len(cues)]
        if bad:
            sys.exit(f"error: --breaks out of range (1..{len(cues)}): {[b + 1 for b in bad]}")
    else:
        starts = group_by_target(cues, args.target)

    scenes = []
    for n, cue_i in enumerate(starts):
        # The first scene always starts at 0, even when the narration does not.
        # A recording that opens with a few seconds of music or silence would
        # otherwise leave the picture with nothing to show there, and since the
        # clips are simply concatenated from video time zero, every scene would
        # land that lead-in early. Holding the opening card over the lead keeps
        # every later cut on its cue.
        start = 0.0 if n == 0 else cues[cue_i]["start"]
        # A scene runs until the next one starts; the last runs to the end of the
        # narration. `duration` is the time the scene is actually on screen —
        # nothing is added for a transition. Baking a tail in here silently
        # delays every later scene by that much once the clips are concatenated,
        # which is exactly the narration drift this pipeline exists to avoid.
        nxt = cues[starts[n + 1]]["start"] if n + 1 < len(starts) else total
        end_i = starts[n + 1] if n + 1 < len(starts) else len(cues)
        scenes.append(
            {
                "index": n + 1,
                "start": round(start, 3),
                "duration": round(nxt - start, 3),
                "layout": "statement",
                "motion": "pan-right" if n % 2 == 0 else "pan-left",
                "kicker": "",
                "headline": "",
                "body": "",
                "bullets": [],
                "narration": [c["text"] for c in cues[cue_i:end_i]],
                "cue_times": [round(c["start"] - start, 2) for c in cues[cue_i:end_i]],
            }
        )

    plan = {
        "design": args.design,
        "resolution": [1920, 1080],
        "fps": 30,
        "audio": args.audio,
        "srt": args.srt,
        "audio_duration": round(total, 3),
        "transition": {"type": "wiperight", "duration": args.transition},
        "scenes": scenes,
    }
    Path(args.output).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"cues: {len(cues)}   scenes: {len(scenes)}   narration: {total:.1f}s")
    print(f"wrote {args.output}")
    for s in scenes:
        head = (s["narration"][0] or "")[:58]
        print(f"  {s['index']:02d}  {s['start']:7.2f}s  {s['duration']:6.2f}s  {head}")
    print("\nNext: write kicker/headline/body/bullets per scene, then render_scenes.py")


if __name__ == "__main__":
    main()

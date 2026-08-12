#!/usr/bin/env python3
"""Chain helper — the mechanical half of generating a video longer than one clip.

`generate_video` animates a still into ONE clip. To go further you feed that
clip's last frame back in as the next clip's first frame. This script owns the
three steps the model must not do by hand:

  preflight    is this sandbox able to do the chain at all?
  last-frame   pull the final frame out of a finished clip
  stitch       join the segments into one file and prove the join is right

Every subcommand prints ONE json object on stdout and exits non-zero on
failure, so a caller reads a result instead of parsing ffmpeg's prose.
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import json
import os
import shutil
import subprocess
import sys
import time

# Where `generate_video` puts a finished clip. The object key is
# ``{conversation_id}/generated/{asset_id}.mp4`` and rclone FUSE-mounts
# ``s3://workspaces/{conversation_id}`` at /workspace, so the clip surfaces here
# about four seconds after the tool returns (measured: 1.5 MB object, visible on
# the second 2s poll, md5 identical through the mount and after a copy off it).
GENERATED_DIR = "/workspace/generated"

# Work lives OFF the mount. /workspace is rclone, and a file written straight
# onto it can read back complete through `cat` and truncated through the
# platform file API — which is the API `capsule_download_url` uses to persist a
# deliverable. Staging to real disk removes that class of failure entirely.
WORK_DIR = "/tmp/video-chain"


def fail(message: str, **extra) -> None:
    print(json.dumps({"ok": False, "error": message, **extra}))
    sys.exit(1)


def done(**fields) -> None:
    print(json.dumps({"ok": True, **fields}))
    sys.exit(0)


def run(cmd: list[str], timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe(path: str) -> dict:
    """Video stream facts for *path*, or raise with ffprobe's own message."""
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,codec_name,r_frame_rate,nb_frames,pix_fmt",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            path,
        ],
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe could not read {path}: {proc.stderr.strip()[-400:]}")
    raw = json.loads(proc.stdout or "{}")
    streams = raw.get("streams") or []
    if not streams:
        raise RuntimeError(f"{path} has no video stream")
    s, f = streams[0], raw.get("format") or {}
    num, _, den = (s.get("r_frame_rate") or "0/1").partition("/")
    fps = (float(num) / float(den)) if den and float(den) else 0.0
    return {
        "path": path,
        "width": int(s.get("width") or 0),
        "height": int(s.get("height") or 0),
        "codec": s.get("codec_name") or "",
        "pix_fmt": s.get("pix_fmt") or "",
        "fps": round(fps, 3),
        "seconds": round(float(f.get("duration") or 0.0), 3),
        "bytes": int(f.get("size") or 0),
    }


def resolve_clip(asset_id: str, wait_seconds: float = 20.0) -> str:
    """Path to the clip `generate_video` saved under *asset_id*.

    Polls, because the tool returns as soon as the object is in storage and the
    mount's directory cache is 2s behind that. A clip that is genuinely absent
    fails with the directory listing attached — the two causes (cache lag vs.
    an unmounted /workspace) need different fixes and must not read alike.
    """
    deadline = time.monotonic() + wait_seconds
    while True:
        hits = sorted(glob.glob(os.path.join(GENERATED_DIR, f"{asset_id}.*")))
        if hits:
            return hits[0]
        if time.monotonic() >= deadline:
            break
        time.sleep(2)

    listing = sorted(os.listdir(GENERATED_DIR)) if os.path.isdir(GENERATED_DIR) else None
    if listing is None:
        fail(
            f"{GENERATED_DIR} does not exist. /workspace is not mounted in this "
            "sandbox, so generated clips cannot be reached from code. Run "
            "`preflight` and report the result — the chain cannot proceed.",
            generated_dir=GENERATED_DIR,
        )
    fail(
        f"no clip for asset {asset_id} in {GENERATED_DIR} after {wait_seconds:.0f}s",
        listing=listing[-20:],
    )
    raise AssertionError("unreachable")


def stage(path: str, tag: str = "") -> str:
    """Copy *path* to real disk under a caller-unique name, and confirm it is whole.

    Two reads of the same source can disagree across the FUSE mount, so the copy
    is checked against a size measured AFTER it, and retried once.

    ``tag`` is not cosmetic. Keyed on the basename alone, two sources named
    ``clip.mp4`` in different directories stage onto ONE file — and since every
    later check reads the staged paths, `stitch` would then probe the survivor
    twice, expect twice its duration, concatenate it twice, measure exactly that,
    and report success for a video with a segment missing and another doubled.
    Every caller staging more than one file must pass a distinct tag.
    """
    os.makedirs(WORK_DIR, exist_ok=True)
    local = os.path.join(WORK_DIR, f"{tag}{os.path.basename(path)}")
    if os.path.abspath(path) == os.path.abspath(local):
        return local
    for attempt in (1, 2):
        shutil.copyfile(path, local)
        src, dst = os.path.getsize(path), os.path.getsize(local)
        if dst > 0 and dst == src:
            return local
        if attempt == 2:
            fail(f"copy of {path} is {dst} bytes against a source of {src}; the read is unstable")
        time.sleep(2)
    raise AssertionError("unreachable")


def cmd_preflight(_: argparse.Namespace) -> None:
    tools = {}
    for name in ("ffmpeg", "ffprobe"):
        which = shutil.which(name)
        tools[name] = which or None
    missing = [n for n, p in tools.items() if not p]

    mount = run(["mountpoint", "-q", "/workspace"], timeout=30)
    mounted = mount.returncode == 0
    clips = (
        sorted(glob.glob(os.path.join(GENERATED_DIR, "*"))) if os.path.isdir(GENERATED_DIR) else []
    )
    free_mb = shutil.disk_usage("/tmp").free // (1024 * 1024)

    ready = not missing and mounted
    remedy = None
    if missing:
        remedy = (
            "sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive "
            "apt-get install -y -qq ffmpeg"
        )
    elif not mounted:
        remedy = (
            "/workspace is not a mountpoint, so a generated clip cannot be read back. "
            "Do not chain: tell the user this agent's sandbox cannot reach generated "
            "clips, and offer single clips instead."
        )

    print(
        json.dumps(
            {
                "ok": ready,
                "ffmpeg": tools["ffmpeg"],
                "ffprobe": tools["ffprobe"],
                "workspace_mounted": mounted,
                "generated_dir": GENERATED_DIR,
                "clips_visible": len(clips),
                "tmp_free_mb": free_mb,
                "remedy": remedy,
            }
        )
    )
    sys.exit(0 if ready else 1)


def match_color(frame_path: str, reference_path: str, strength: float) -> None:
    """Pull *frame_path*'s per-channel mean and spread back toward *reference_path*.

    Optional, and off by default. Each generation shifts exposure and saturation
    a little; over four or five links those shifts compound in one direction and
    the last segment no longer looks like the first. Blending part-way back
    toward the opening frame arrests that without repainting the image.

    It is a TRADE. Only the handoff frame is corrected — the clip before it still
    ends on the uncorrected one — so the seam carries a one-frame step of roughly
    a single link's drift, in exchange for drift that no longer grows with the
    chain. Worth it past four links; actively worse below that, which is why the
    caller has to ask for it.
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on the image
        fail(f"--match-color needs Pillow and numpy in the sandbox: {exc}")

    src = np.asarray(Image.open(frame_path).convert("RGB"), dtype=np.float32)
    ref = np.asarray(Image.open(reference_path).convert("RGB"), dtype=np.float32)

    out = src.copy()
    for c in range(3):
        s_mean, s_std = float(src[..., c].mean()), float(src[..., c].std())
        r_mean, r_std = float(ref[..., c].mean()), float(ref[..., c].std())
        if s_std < 1e-3:
            continue
        # Full correction, then blended — so strength=0 is a no-op and
        # strength=1 lands exactly on the reference's statistics.
        corrected = (src[..., c] - s_mean) * (r_std / s_std) + r_mean
        out[..., c] = src[..., c] + (corrected - src[..., c]) * strength

    Image.fromarray(np.clip(out, 0, 255).astype("uint8")).save(frame_path)


def cmd_last_frame(args: argparse.Namespace) -> None:
    clip = args.clip or resolve_clip(args.asset)
    local = stage(clip)
    facts = probe(local)
    if facts["seconds"] <= 0:
        fail(f"{clip} reports a duration of 0 — it is not a finished clip", clip=facts)

    os.makedirs(WORK_DIR, exist_ok=True)
    scratch = os.path.join(WORK_DIR, "tail")
    shutil.rmtree(scratch, ignore_errors=True)
    os.makedirs(scratch)

    # Decode the last ~1.2s to PNG and pick from the end, rather than seeking to a
    # computed timestamp. The frame count is then something we COUNT instead of
    # something we trust nb_frames to report, and --from-end works the same way on
    # a clip of any length or rate.
    proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-sseof",
            "-1.2",
            "-i",
            local,
            "-vsync",
            "0",
            os.path.join(scratch, "f_%04d.png"),
        ]
    )
    frames = sorted(glob.glob(os.path.join(scratch, "f_*.png")))
    if proc.returncode != 0 or not frames:
        fail(f"could not decode the tail of {clip}: {proc.stderr.strip()[-400:]}")
    if args.from_end > len(frames):
        fail(
            f"--from-end {args.from_end} but only {len(frames)} frames were decoded "
            "from the clip's last 1.2s",
            frames_available=len(frames),
        )

    chosen = frames[-args.from_end]
    out = args.out or os.path.join(WORK_DIR, "next-first-frame.png")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    shutil.copyfile(chosen, out)

    if args.match_color:
        match_color(out, args.match_color, args.match_strength)

    # A frame whose size does not match the clip would change the preset the next
    # generation resolves to, and a preset change mid-chain is what makes the
    # segments refuse to concatenate later.
    try:
        from PIL import Image

        with Image.open(out) as img:
            fw, fh = img.size
    except ImportError:
        fw = fh = 0
    if fw and (fw, fh) != (facts["width"], facts["height"]):
        fail(
            f"extracted frame is {fw}x{fh} but the clip is {facts['width']}x{facts['height']}",
            clip=facts,
        )

    shutil.rmtree(scratch, ignore_errors=True)
    done(
        frame_path=out,
        source=clip,
        from_end=args.from_end,
        frames_decoded=len(frames),
        color_matched=bool(args.match_color),
        clip=facts,
    )


def cmd_stitch(args: argparse.Namespace) -> None:
    if args.assets:
        sources = [resolve_clip(a.strip()) for a in args.assets.split(",") if a.strip()]
    else:
        sources = [p.strip() for p in (args.clips or "").split(",") if p.strip()]
    if len(sources) < 2:
        fail("stitch needs at least two clips", given=sources)

    staged = [stage(p, f"{i:02d}-") for i, p in enumerate(sources)]
    facts = [probe(p) for p in staged]

    shapes = {(f["width"], f["height"]) for f in facts}
    if len(shapes) > 1:
        fail(
            "the segments are not all the same size, so they cannot be joined into "
            "one clip. This happens when a first frame changed aspect ratio mid-chain.",
            shapes=[f"{w}x{h}" for w, h in sorted(shapes)],
            segments=facts,
        )

    expected = round(sum(f["seconds"] for f in facts), 3)
    os.makedirs(WORK_DIR, exist_ok=True)
    list_path = os.path.join(WORK_DIR, "concat.txt")
    with open(list_path, "w") as fh:
        for p in staged:
            fh.write(f"file '{os.path.abspath(p)}'\n")

    out = args.out
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    uniform = len({(f["codec"], f["pix_fmt"], f["fps"]) for f in facts}) == 1
    attempts = []
    if uniform and not args.reencode:
        attempts.append(
            (
                "copy",
                [
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    list_path,
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    out,
                ],
            )
        )
    attempts.append(
        (
            "reencode",
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path,
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                out,
            ],
        )
    )

    problems = []
    for mode, tail in attempts:
        proc = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *tail], timeout=280)
        if proc.returncode != 0:
            problems.append(f"{mode}: {proc.stderr.strip()[-300:]}")
            continue
        result = probe(out)
        # The join is only correct if the whole timeline survived it. A stream copy
        # across clips with mismatched timebases can produce a file that plays and
        # is seconds short, which no amount of watching the first segment reveals.
        if abs(result["seconds"] - expected) > 0.3:
            problems.append(
                f"{mode}: joined to {result['seconds']}s against an expected {expected}s"
            )
            continue
        done(
            output=out,
            mode=mode,
            segments=len(staged),
            seconds=result["seconds"],
            expected_seconds=expected,
            width=result["width"],
            height=result["height"],
            bytes=result["bytes"],
        )

    # Every attempt failed, so nothing may remain at ``out``. ffmpeg writes as it
    # goes, and a rejected join leaves a file that is a plausible video — short by
    # a segment, but complete-looking, at exactly the path the caller was about to
    # publish. The result says ok:false; the artifact must not say otherwise.
    with contextlib.suppress(OSError):
        os.remove(out)
    fail("could not join the segments", attempts=problems, expected_seconds=expected)


def cmd_probe(args: argparse.Namespace) -> None:
    path = args.path
    if not os.path.exists(path) and "/" not in path:
        path = resolve_clip(path)
    done(**probe(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("preflight", help="check ffmpeg and the workspace mount").set_defaults(
        func=cmd_preflight
    )

    lf = sub.add_parser("last-frame", help="extract a finished clip's final frame")
    lf.add_argument("--asset", help="asset_id returned by generate_video")
    lf.add_argument("--clip", help="path to the clip, instead of --asset")
    lf.add_argument("--out", help="where to write the PNG (default /tmp/video-chain/…)")
    lf.add_argument(
        "--from-end",
        type=int,
        default=1,
        help="1 = the last frame (default). Raise to 2-3 only if the last frame is "
        "motion-blurred; every frame skipped is a visible jump at the seam.",
    )
    lf.add_argument("--match-color", help="reference PNG to pull exposure back toward")
    lf.add_argument("--match-strength", type=float, default=0.5)
    lf.set_defaults(func=cmd_last_frame)

    st = sub.add_parser("stitch", help="join the segments and verify the join")
    st.add_argument("--assets", help="comma-separated asset ids, in order")
    st.add_argument("--clips", help="comma-separated paths, in order")
    st.add_argument("--out", required=True)
    st.add_argument("--reencode", action="store_true", help="skip the stream-copy attempt")
    st.set_defaults(func=cmd_stitch)

    pr = sub.add_parser("probe", help="size, duration and codec of a clip or asset id")
    pr.add_argument("path")
    pr.set_defaults(func=cmd_probe)

    args = parser.parse_args()
    if args.cmd == "last-frame" and not (args.asset or args.clip):
        parser.error("last-frame needs --asset or --clip")
    try:
        args.func(args)
    except subprocess.TimeoutExpired as exc:
        fail(f"{exc.cmd[0] if exc.cmd else 'command'} timed out after {exc.timeout}s")
    except Exception as exc:  # noqa: BLE001 - the caller reads json, never a traceback
        fail(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()

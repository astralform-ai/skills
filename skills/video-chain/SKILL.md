---
name: video-chain
description: Build a video longer than a single generation by chaining clips — animate a still, take the clip's last frame, animate that, repeat until the requested length, then join the segments into one continuous file. Use when the user asks for a video of a specific duration (15s, 30s, a minute), for a longer or continuous shot, to keep going, or to extend or continue a clip that has already been generated. Requires video mode and a source image already in the conversation.
display_name: Video Chain
version: "1.0.0"
author: Astralform
---

# Video Chain

`generate_video` makes ONE clip, about five seconds long. A thirty-second video
is not a longer call — it is six clips, where each one starts on the frame the
one before it ended on, and they are joined at the end.

That handoff is the whole skill. Everything below exists to keep the seam
invisible and to stop you spending twenty minutes of shared GPU on segments that
turn out not to join.

## The one law

**The last frame is the next prompt's subject.** You are never describing the
scene again — the frame already carries it. Each prompt describes only what
moves during the next five seconds, and where the motion should come to rest,
because that resting frame is what the following segment has to start from.

A prompt that re-describes the subject fights the frame and the chain drifts.
See `references/continuity.md` before writing the shot list.

## Before you generate anything

Three preconditions, all cheap to check and expensive to discover late.

1. **Video mode must be on.** `generate_video` is attached only to a turn the
   user put in video mode. If you do not have the tool, say so plainly — the
   user flips it in the composer — and stop.
2. **A source still must already exist in this conversation.** A video-mode turn
   carries no `generate_image`, by design: the first frame is the caller's to
   supply, as an attachment or as a still generated in an earlier image-mode
   turn. If there is none, ask for one instead of guessing.
3. **The sandbox must be able to read generated clips.** Run the preflight
   below. If it fails on the mount, do not start a chain you cannot finish.

```python
import capsule
SK = "{baseDir}"

def run(cmd, timeout=280):
    """proc.exec never raises — an unchecked call looks like success while
    producing nothing, so read the result every time."""
    r = capsule.proc.exec(cmd, timeout=timeout)
    if r["stdout"]:
        print(r["stdout"])
    if r["stderr"]:
        print(r["stderr"][-1000:])
    return r

run(f"python3 {SK}/scripts/chain.py preflight")
```

`ok: false` with a `remedy` is an instruction, not a warning. Missing ffmpeg is
one `apt-get` away; an unmounted `/workspace` is not fixable from here — tell
the user this agent's sandbox cannot reach generated clips and offer single
clips instead.

Note that video mode requires `generate_video` on the first model call of the
turn, so a first clip often already exists by the time you read this. That is
fine: treat it as segment 1 and chain from its last frame.

## Do the arithmetic out loud, and get a go-ahead

One segment costs about **four minutes** on a GPU shared with every other agent,
and clips generate strictly one at a time. So:

| Asked for | Segments | Rough wait |
|---|---|---|
| 10s | 2 | ~8 min |
| 30s | 6 | ~25 min |
| 60s | 12 | ~50 min |

Do not read "five seconds" off this page — read `seconds` out of the first
`generate_video` result, which reports what this agent's configuration actually
produced, and divide the target by that. Round up; a chain overshoots rather
than delivering short.

State the segment count and the wait **before the first generation**, and for
anything over about six segments get an explicit go-ahead. Twenty-five minutes
of silence that the user did not agree to is the failure mode here, not a
technical one.

## The loop

Segment 1 is `generate_video` against the user's still. Every segment after it
is the same three calls.

**a. Pull the last frame of the clip you just made.** The result of
`generate_video` is json carrying `asset_id`; that is all the script needs.

```python
run(f"python3 {SK}/scripts/chain.py last-frame "
    f"--asset 7f3c9e21-… --out /tmp/video-chain/seg-03-start.png")
```

**b. Turn that frame into an asset the tool can accept.** `generate_video` takes
a `source_asset_id`, not a path, so the frame has to be recorded against this
conversation first:

```
capsule_download_url("/tmp/video-chain/seg-03-start.png")
```

It answers `Download URL: https://…/chat/<conversation_id>/files/<asset_id>`.
**The last path segment is the asset id** — that is what you pass next. These
frames land in the conversation's files, so name them `seg-NN-start.png` and
they read as working files rather than clutter.

**c. Generate the next segment** with `generate_video`, passing that asset id and
the prompt for shot N from your list.

Repeat. Keep a running list of `(segment, clip asset_id, seconds)` as you go —
you need the ids in order at the end, and you need the running total to know
when to stop.

**One `generate_video` call per response.** Two in one response are dispatched in
parallel onto one GPU; you are billed for both and neither is the other's
continuation.

## Join and deliver

```python
run(f"python3 {SK}/scripts/chain.py stitch "
    f"--assets id1,id2,id3,id4,id5,id6 --out /tmp/video-chain/final.mp4")
run(f"python3 {SK}/scripts/chain.py probe /tmp/video-chain/final.mp4")
```

`stitch` joins by stream copy where it can, re-encodes where it cannot, and
**verifies the joined duration against the sum of the parts**. A stream copy
across clips with mismatched timebases produces a file that plays perfectly and
is seconds short — watching the opening never reveals it, which is why the check
is not optional. A failure here names which segment disagrees.

Then deliver:

```
capsule_download_url("/tmp/video-chain/final.mp4")
```

Keep the file in `/tmp` and let that tool persist it. Writing a finished video
onto `/workspace` invites the mount's read incoherency, where the file is whole
to `cat` and truncated to the API that publishes it.

Give the user the returned link as-is, and say what they are getting: length,
segment count, no audio. Never embed it with `![…](…)` — it is a page, not video
bytes.

## Gotchas

These are properties of the pipeline, not of any one run.

1. **No audio, ever.** `generate_video` produces silent clips and the join keeps
   them silent. Do not promise sound; if the user wants narration or music, that
   is a separate pass with ffmpeg over the finished master.
2. **Shape locks in after segment 1.** The preset is chosen from the first
   frame's aspect ratio, and from segment 2 the first frame IS a clip frame — so
   every later segment inherits the first one's shape. That is what makes the
   stream-copy join possible. It also means a wrong shape at segment 1 is wrong
   for the whole video: check the source still's orientation before starting.
3. **Drift is real and one-directional.** Each pass shifts exposure and
   saturation slightly, and the shifts compound. Below four segments it is
   invisible. Past that, either pass `--match-color seg-01-start.png` to
   `last-frame` (it pulls the frame's levels part-way back toward the opening
   one), or re-anchor: start a fresh chain from a new still and treat the result
   as a cut.
4. **A blurred last frame propagates.** If a segment ends mid-motion, its final
   frame is motion-blurred and the next segment starts from blur. Prefer prompts
   that come to rest. `--from-end 2` steps back one frame as a repair, but every
   frame skipped is a visible jump at the seam — fix the prompt first.
5. **Generation failures come back as text, not exceptions.** `generate_video`
   returns a sentence describing what went wrong and the run continues. Read
   every result. Retrying costs another four minutes, so retry a segment only
   once, then stop and report.
6. **A clip takes a moment to appear.** The tool returns when the clip is in
   storage; the sandbox sees it about four seconds later (measured), because the
   mount refreshes its directory listing on an interval. `chain.py` waits for it
   — do not add sleeps of your own, and do not conclude a clip is missing
   because a first `ls` did not show it.

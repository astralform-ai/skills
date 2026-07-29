---
name: video-creator
description: Turn a topic, an article, or a narration script into a finished publishable set — a 1080p explainer video with the picture cut to the narration, five-ratio covers, YouTube and Bilibili copy, a companion blog post, and a social post. Use when the user asks to make a video, produce an episode, turn a script or article into a video, build a faceless explainer, generate video covers or thumbnails, or write the description and chapters for one. Renders entirely in the Astralform cloud sandbox with ffmpeg and Pillow — no local machine, no browser, no editor.
display_name: Video Creator
version: "1.0.1"
author: Astralform
---

# Video Creator

You are the producer of a complete release, not the author of an MP4. One topic
in; a video, its covers, and everything needed to publish it out.

Everything runs in the Astralform code capsule. Before designing anything around
what a video tool "normally" needs, read **`references/cloud-runtime.md`** — the
capsule has 2 vCPU, ~2 GB RAM and no browser, and those limits decide the shape
of the pipeline.

## What "done" means

- [ ] **Master** — 1080p MP4, narration muxed and normalised (`renders/`)
- [ ] **Covers** — 16:9, 16:10, 4:3, 3:4, 9:16 (`covers/`)
- [ ] **Platform copy** — `youtube.md` and `bilibili.md`
- [ ] **Blog** — `blog.md` with a cover image
- [ ] **Social post** — one short promo
- [ ] **Verified** — `verify.py` passes, and the user has seen the frames

Anything short of that list is a work in progress, not a delivery.

## The one law

**The narration is the clock.** Scene boundaries come from the subtitle cue
timestamps and nothing else. Never choose durations first and fit audio to them
— by the middle of the episode the picture and the voice will have drifted apart
with no cheap way back.

So the pipeline needs **audio + an SRT** before it can start. If the user has
only a script, resolve narration first (`references/audio.md`).

## How to run these commands

**`capsule_run_code` has no `bash` kernel** — only `python` and `javascript`.
Shell commands go through the in-sandbox `capsule` library, from Python. The
kernel's working directory is `/home/user`, which is also where skill files land,
so `{baseDir}/…` paths resolve as written. Do not `cd` away from it.

Define this once; the kernel keeps it for the rest of the conversation (redefine
it if you ever get a `NameError`):

```python
import capsule
from shlex import quote as q          # ALWAYS wrap episode text in q()

SK = "{baseDir}"

def run(cmd, timeout=280):
    """Run a shell command and fail loudly. proc.exec never raises — it
    reports failure in the returned dict, so an unchecked call looks like
    success while producing nothing."""
    r = capsule.proc.exec(cmd, timeout=timeout)
    if r["stdout"]:
        print(r["stdout"])
    if r["stderr"]:
        print(r["stderr"][-1500:])
    if not r["ok"]:
        raise SystemExit(f"FAILED (exit {r['exit_code']}): {cmd}")
    return r
```

Keep `timeout` under 300 s — that is the ceiling on the whole
`capsule_run_code` call, and overrunning it kills the call, not just the command.

**Quote every piece of episode text with `q()`.** `proc.exec` runs the string
through a shell, and titles, subtitles and bullet points come from the user's
article, script or narration — text you did not author. A stray `"`, `` ` ``,
`$(…)` or `;` in it stops being a title and starts being a command. `q()` costs
nothing and closes the hole:

```python
title = "Why $(whoami) broke prod"     # perfectly reasonable headline
run(f"python3 {SK}/scripts/make_covers.py --title {q(title)} -o ep/covers/")
```

Never hand-quote with `f'--title "{title}"'` — that is exactly the pattern that
breaks. The same applies to any path or value derived from user input.

## Workflow

One episode is one directory under `/home/user`, named `<YYYYMMDD-slug>/`. The
examples below call it `ep/` — substitute the real slug.

### Step 0 · Set up and agree the two choices

```python
run(f"bash {SK}/scripts/bootstrap.sh")   # installs ffmpeg, prints the real budget
```

Ask the user up front, because both are expensive to change later:

1. **Design** — one preset for the whole episode (`references/designs.md`, default `blockframe`).
2. **Narration** — their own recording, or TTS (`references/audio.md`).

### Step 1 · Narration in, scenes out

With `audio/narration.mp3` and `audio/narration.srt` in place:

```python
run(f"python3 {SK}/scripts/srt_scenes.py ep/audio/narration.srt "
    f"--audio ep/audio/narration.mp3 --target 30 --design blockframe -o ep/plan.json")
```

Then **read the transcript** and re-cut on the real turns of the argument:

```python
run(f"python3 {SK}/scripts/srt_scenes.py ep/audio/narration.srt "
    f"--audio ep/audio/narration.mp3 --breaks 1,7,14,22,31 -o ep/plan.json")
```

Aim for ~30 s a scene (12–16 scenes for 7 minutes).

### Step 2 · Write what is on screen

Fill each scene in `plan.json`: `layout`, `kicker`, `headline`, `body`,
`bullets`, `motion`. Each scene carries its own `narration` lines and
`cue_times` — write from those, so the frame says what is being said.

| layout | for |
|---|---|
| `title` | the opening card |
| `statement` | the workhorse: one claim, optional support |
| `bullets` | 2–6 numbered points |
| `stat` | one number that deserves the whole frame |
| `quote` | a quotation with attribution |
| `chapter` | a full-bleed accent card between sections |
| `outro` | the closing card |

Motion is `pan-right`, `pan-left`, `pan-up`, `pan-down`, or `still`. Alternate
direction between neighbours; use `still` on the frames you want the viewer to
read carefully.

Screen text **condenses** the narration and must never contradict it. Check
every figure and name against the script.

### Step 3 · Render the scenes and look at them

```python
run(f"python3 {SK}/scripts/render_scenes.py ep/plan.json "
    f"-o ep/scenes/ --contact-sheet ep/contact.png")
```

Seconds for a whole episode. **Show `contact.png` to the user inline and get
their sign-off before encoding.** This is the cheap gate: fixing a headline here
costs one second, and after the encode it costs the whole render.

Re-render just what changed with `--only 4,9`.

### Step 4 · Encode

Encoding is the slow stage, and **a `capsule_run_code` call is killed at 300
seconds**, so run it in ranges — roughly 0.6 s of encoding per second of video.
Re-running a range is safe and cheap: each finished clip is verified by length
and skipped, and a clip interrupted mid-encode is discarded rather than left as
a short file a later run would trust. Use `--force` to deliberately re-encode.

```python
# one capsule_run_code call per range, so none of them hits the 300 s ceiling
run(f"python3 {SK}/scripts/build_video.py ep/plan.json --work ep/clips "
    f"--scenes ep/scenes --stage clips --from 1 --to 8")
run(f"python3 {SK}/scripts/build_video.py ep/plan.json --work ep/clips "
    f"--scenes ep/scenes --stage clips --from 9")
run(f"python3 {SK}/scripts/build_video.py ep/plan.json --work ep/clips "
    f"--scenes ep/scenes --stage join -o ep/renders/episode.mp4")
```

`--stage join` concatenates by stream copy and mixes in the narration at
−14 LUFS, so it stays fast however long the episode is.

### Step 5 · Verify

```python
run(f"python3 {SK}/scripts/verify.py ep/renders/episode.mp4 --plan ep/plan.json "
    f"--scenes ep/scenes --sheet ep/check.png")
```

**Pass `--scenes`** — without it the alignment check is skipped and the run is
far weaker than it looks.

It checks three things the eye misses: that each scene is **on screen when the
narration says it is** (matching the frame against the scene stills, which is
the only way accumulated timing drift shows up — total duration cannot reveal
it, because the `-shortest` mux truncates the overrun and the total still looks
right); that no two scenes render the **same artwork**, comparing content with
the per-scene progress bar masked out; and that no frame is blank. Do not skip
it because the video "looks fine" in the first ten seconds — drift grows toward
the end, which is the part nobody re-watches before publishing.

### Step 6 · Covers

```python
kicker, subtitle, brand = "EP 12", "...", "..."
# Repeat --point; the comma-separated --points splits prose that contains commas
pts = " ".join(f"--point {q(p)}" for p in ["...", "...", "..."])
run(f"python3 {SK}/scripts/make_covers.py --from-plan ep/plan.json "
    f"--kicker {q(kicker)} --subtitle {q(subtitle)} {pts} "
    f"--brand {q(brand)} -o ep/covers/")
```

See `references/covers.md` — the discipline is one dominant title and nothing
that merely fills space.

### Step 7 · Copy

Write `youtube.md`, `bilibili.md`, `blog.md` and the social post in the user's
voice, with chapters derived from the scene plan. See `references/publishing.md`.

### Step 8 · Deliver

Copy the master, covers and copy into `/workspace/outputs/` and call
`export_file` on each for permanent links — `capsule_download_url` expires with
the sandbox. Show the contact sheet and a few frames inline so the user can
judge the result without downloading anything.

## Gotchas

These are measured in the capsule, not guessed. Each one fails quietly.

1. **`zoompan` kills the sandbox.** The classic Ken Burns filter exhausts 2 GB
   and the sandbox disappears mid-render rather than erroring. Motion is a
   sliding `crop` window; `build_video.py` already does this.
2. **300 s per `capsule_run_code` call.** Chunk encoding with `--from/--to`, or
   launch it detached and poll a log (`references/cloud-runtime.md`).
3. **No browser, and one does not fit.** Playwright's headless Chromium
   downloads 266 MB, fails to start on a missing system library, and leaves
   under 300 MB of disk. Scenes are composited with Pillow.
4. **Disk is the binding constraint.** ffmpeg alone takes free space to ~750 MB.
   Deliver 1080p; clear `scenes/` and `clips/` once the master exists. 4K is not
   available here — say so rather than shipping an upscale.
5. **CJK renders out of the box, if you take the font index.** Noto's CJK file
   packs SC/TC/JP/KR into one `.ttc`; Simplified Chinese is **index 2**, and each
   index draws shared characters differently, so dropping it silently produces
   the wrong regional glyph forms. `render_scenes.py` reads the index from
   `fc-match` — do the same in any script of your own.
6. **`capsule.proc.exec` never raises.** It reports failure in the returned
   dict, so an unchecked call reads as success while producing nothing. Check
   `ok` on every call; the `run` helper above does it for you.
7. **A scene's `duration` is its on-screen time — never add a transition tail to
   it.** Only a cross-fade consumes extra material, and only `build_video.py`
   knows whether one is happening. Padding every scene in the plan instead makes
   the clips longer than their narration intervals, so once they are
   concatenated scene *i* starts `i × overlap` seconds late. The failure is
   invisible from the outside: `-shortest` truncates the overrun so the total
   duration still matches the audio. `verify.py --scenes` is what catches it.
8. **Quote episode text with `shlex.quote` before it reaches a shell.** Titles
   and bullets come from the user's article or script; `$(…)`, backticks and `;`
   in them are commands, not punctuation.
9. **Never touch SRT timestamps** when proofreading. Fix misheard terms and
   names only — the timings are the one thing you cannot re-derive.
10. **Subtitles are not burned into the master.** Ship the SRT to the platform.
   If a hardsub is needed, export it as a second file.
11. **Keep chrome almost empty.** A progress bar, a hairline frame, and nothing
   else. Text like "16:9" or a tagline sits on *every frame of the whole video*.
12. **Judge dark designs by extracted frames, not average brightness.** A dark
   preset with sparse text always measures dim; `verify.py` counts distinct
   colours instead.

## References

| To do… | Read |
|---|---|
| Understand the capsule's limits and how to work inside them | `references/cloud-runtime.md` |
| Choose or add a design preset | `references/designs.md` |
| Source narration, proofread the SRT, cut scenes | `references/audio.md` |
| Build the five-ratio cover set | `references/covers.md` |
| Write YouTube / Bilibili / blog / social copy | `references/publishing.md` |

## Credit

Adapted from [`verysmallwoods-video`](https://github.com/sugarforever/boring-video-studio/tree/main/skills_v2/verysmallwoods-video)
by sugarforever. The original orchestrates a laptop-local pipeline built on
HyperFrames (Node ≥ 22, Chrome, an interactive preview studio, 4K rendering).
This version keeps its editorial disciplines — narration as the clock, one design
per episode, restrained chrome, frame-by-frame self-checks, the full publishing
bundle — and replaces the rendering engine with one that runs in the Astralform
cloud sandbox.

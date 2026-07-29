# Narration

**The narration is the clock.** Scene boundaries are read off the subtitle cue
timestamps, never chosen by feel. Get this backwards — pick durations first,
then squeeze audio in — and the picture drifts out of sync with the voice by the
middle of the episode, with no cheap way back.

So this skill takes two inputs and will not start without them:

- an audio file (`mp3` / `wav` / `m4a`), and
- an **SRT** with real timestamps.

## Where the pair comes from

**The user recorded it.** Best quality, and the usual case for a personal
channel. They hand you both files; most editors export an SRT.

**Text-to-speech.** The capsule has no TTS engine of its own, and no browser to
drive a hosted one, so synthesis happens outside this skill: use whichever TTS
the agent has a connector or API key for, then bring the audio **and the
timings** back. Any TTS worth using returns word or sentence timings — keep
them. Ask for the SRT rather than reconstructing it.

**Audio but no SRT.** Ask before doing anything else. Users often withhold an
SRT deliberately (a draft, a re-record coming). Do not silently transcribe. And
do not reach for a speech-recognition model inside the capsule: after ffmpeg
there is roughly 750 MB of disk and 2 vCPU left, which is a bad home for one.
Transcribe elsewhere, or ask the user to export the SRT.

**Only a script, no audio.** Then there is nothing to time against. Say so, and
resolve narration first.

## Proofreading the SRT

Read it against the script and fix **only** what was misheard: terminology,
proper nouns, homophones. **Never touch a timestamp.** The timestamps are the
one thing you cannot re-derive, and the whole edit hangs off them.

## From cues to scenes

`{baseDir}/scripts/srt_scenes.py` does the arithmetic:

```
scene[i].start    = the first cue in the scene
scene[i].duration = scene[i+1].start − scene[i].start
last scene        = runs to the end of the narration
```

`duration` is the time the scene is **on screen**, and nothing is added to it for
a transition. Only a cross-fade needs extra material, and only `build_video.py`
knows whether one is happening — so it extends the clip at encode time. Padding
the plan instead makes every clip longer than its narration interval, and once
they are concatenated scene *i* starts `i × 0.5 s` late.

Run it once with `--target` for a rough grid, **read the transcript**, then re-cut
with `--breaks` where the argument actually turns:

```python
run(f"python3 {SK}/scripts/srt_scenes.py ep/audio/narration.srt "
    f"--audio ep/audio/narration.mp3 --target 30 -o ep/plan.json")
# ...read the transcript, then re-cut on the real turns:
run(f"python3 {SK}/scripts/srt_scenes.py ep/audio/narration.srt "
    f"--audio ep/audio/narration.mp3 --breaks 1,7,14,22,31 -o ep/plan.json")
```

Aim for roughly **30 seconds a scene** — around 12–16 scenes for a 7-minute
piece. Much longer and the frame sits still while the voice keeps going; much
shorter and it flickers.

Each scene in the plan carries its `narration` lines and `cue_times` (seconds
relative to the scene start). Use them to decide what belongs on screen: a
number that gets said 6 seconds in belongs in that scene, not the previous one.

## On-screen copy versus what is said

Screen text is a **condensation** of the narration, never a contradiction. It
may be a tighter, poster-like phrasing of the same point; it may not assert
something different from what the viewer is hearing. Check figures and names
against the script as you write them — these are exactly what viewers catch.

## Loudness

Recorded and synthesised narration both tend to be quiet. `build_video.py`
normalises to **−14 LUFS** (the streaming target) while copying the video
stream, so it costs seconds rather than a re-render. Pass `--no-normalise` only
if the audio was already mastered.

## Subtitles are not burned in

The master ships without hard subtitles; upload the proofread SRT to the
platform instead. Viewers can then turn them off, and the same master serves
every language you later add. Layouts already leave the lower band clear for the
player's own subtitle rendering.

If a specific platform genuinely needs burned-in captions, make it a **separate
export** and keep the clean master:

```python
style = "FontName=Noto Sans CJK SC,FontSize=22,BorderStyle=3,Outline=1"
vf = f"subtitles=ep/audio/narration.srt:force_style='{style}'"
run(f'ffmpeg -y -i ep/renders/episode.mp4 -vf "{vf}" '
    f"-c:a copy ep/renders/episode-hardsub.mp4")
```

## If the delivery is slow

For a speaker who reads slowly, speed the audio up **before** timing anything,
and scale the SRT by the same factor — otherwise every cue is wrong:

```python
run('ffmpeg -y -i raw.mp3 -af "atempo=1.1,loudnorm=I=-14:TP=-1.5:LRA=11" '
    'ep/audio/narration.mp3')
```

Then confirm the new duration is the original divided by 1.1, and re-derive the
scene plan from the rescaled SRT. Do not do this after building scenes.

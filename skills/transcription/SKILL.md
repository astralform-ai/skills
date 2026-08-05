---
name: transcription
description: "Turning speech into text — audio and video files, recordings, podcasts, meetings, voice memos, lecture captures, interviews. Use whenever you need to know what was said in a recording, or the user sends one and asks what is in it. Also trigger on 'transcribe this', 'what does this audio say', 'summarize this recording/meeting/podcast', 'pull quotes from this video', or when a video has no captions to read."
display_name: Transcription
version: "1.0.0"
author: Astralform
---

# Transcription

You have no native audio input. A recording is opaque to you until it is transcribed — so
transcribe first, then work on the text like any other document.

## The tool

```
transcribe_audio(source="...", language="en")
```

Returns the transcript as `[MM:SS]` lines, so you can quote and link specific moments.

`language` is an ISO-639-1 **hint**, not a filter. Pass it when you know it, omit it to
auto-detect. Passing the wrong one is worse than passing none.

## What `source` accepts

Three forms. Picking the right one saves a download you do not need:

| Form | Use when | Example |
|---|---|---|
| **Conversation asset id** | The user attached the file | the asset id from the attachment |
| **http(s) URL** | The file is already a direct audio/video URL | `https://.../ep-14.mp3` |
| **Sandbox path** | You produced or fetched the file yourself | `/workspace/audio/clip.mp3` |

An attached recording does **not** need to be downloaded into the sandbox first — pass the
asset id straight to the tool. Likewise a direct media URL: hand over the URL and let the
backend fetch it.

A sandbox path is for when neither applies: you extracted audio from a video, split a long
file, or pulled media off a page.

### Getting to one of those three

```bash
# Audio out of a video file you already have — -vn drops the video stream.
ffmpeg -i /workspace/input.mp4 -vn -c:a libmp3lame /workspace/audio/input.mp3

# Media off a page (not a direct file URL). -x extracts audio, so no video is downloaded.
pip install yt-dlp   # not pre-installed; ffmpeg and deno, which it needs, are
yt-dlp -f 'bestaudio/best' -x --audio-format mp3 -o '/workspace/audio/%(title)s.%(ext)s' 'URL'
```

`ffmpeg` is already in the sandbox. `yt-dlp` is **not** — `pip install yt-dlp` first; it is
a small, fast install. (`deno` *is* baked in, precisely because yt-dlp needs it: without it
yt-dlp silently drops to a degraded path that misses formats.) For YouTube specifically, use the
**youtube** skill — published captions are faster and cheaper than transcribing, so it tries
those first and only falls back here.

## What to expect

- **Seconds, not minutes.** A hosted provider handles a 30-minute recording in under ten
  seconds. If it is taking minutes, it fell back to in-sandbox transcription — still correct,
  roughly real-time.
- **The tool picks the provider.** Credentials live in the backend and never enter the
  sandbox. There is nothing to configure and no API key to look for — if you catch yourself
  hunting for one in `os.environ`, that is the wrong path.
- **Timestamps come back automatically.** Do not ask for them separately.
- **A failure is a returned message, not an exception.** Read the string you get back; it
  says which failure it is.

## Long recordings

A single request caps at ~25 MB. A ~30-minute recording as mp3 fits comfortably. If the tool
refuses because the file is too large, split it, transcribe each part, then offset each
part's timestamps by where that part started:

```bash
# 20-minute chunks; -c copy avoids re-encoding.
ffmpeg -i /workspace/audio/full.mp3 -f segment -segment_time 1200 -c copy /workspace/audio/part%03d.mp3
```

The second chunk's `[00:15]` is `[20:15]` in the full recording. Say the real time, not the
chunk-relative one — a timestamp that does not match what the user hears is worse than no
timestamp.

## Do not

- **Do not install whisper, faster-whisper, or torch.** They are already in the sandbox, and
  `transcribe_audio` uses them. Installing again burns minutes and fills the disk.
- **Do not download model weights.** They ship with the image. A download will be slow or
  fail outright — the model hosts are not reliably reachable from a sandbox.
- **Do not report "I can't listen to audio".** You can read it. That is what this tool is.

## Handing over the result

A transcript of any length belongs in a file, not in the reply — see the **export** skill.
Put the summary or the quotes the user asked for in your reply, and the full transcript in
the file.

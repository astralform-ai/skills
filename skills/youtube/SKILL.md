---
name: youtube
description: "YouTube video transcript extraction and content analysis. Use whenever a user shares a YouTube URL, asks to transcribe/summarize/analyze a video, wants quotes or key points from a video, mentions extracting subtitles or captions, or needs to compare multiple videos. Also trigger when users say things like 'watch this video', 'what does this video say', 'get the transcript', 'summarize this talk', 'who are the speakers', or provide any youtube.com / youtu.be link."
display_name: YouTube
version: "1.0.0"
author: Astralform
---

# YouTube

Extract transcripts from YouTube videos and analyze their content — summaries, key points, speaker identification, quotes, topic extraction, and more. No API key required.

## When to Use

- User shares a YouTube URL (any format) and wants to understand its content
- User asks for a transcript, subtitles, or captions from a video
- User wants a summary, key points, or takeaways from a video
- User asks "what does this video say about X"
- User wants to compare content across multiple videos
- User needs quotes, timestamps, or specific moments from a video
- User is researching a topic and wants to extract information from video sources

## Prerequisites

**Required:** `yt-dlp` — the universal video/subtitle downloader.

The script auto-installs `yt-dlp` via `pip` if it's not found, so no manual setup is needed in most environments (including sandboxed runtimes like E2B). If auto-install fails, install manually:

```bash
pip install yt-dlp
```

## Phase 1: Extract

Use the bundled script at `{baseDir}/scripts/fetch_transcript.py` to handle transcript downloading, SRT parsing, deduplication, sentence segmentation, and caching. `{baseDir}` is the directory containing this SKILL.md — resolve it to the actual path before running.

### Basic Usage

```bash
# Get structured JSON (metadata + clean sentences with timestamps)
python3 '{baseDir}/scripts/fetch_transcript.py' 'YOUTUBE_URL'

# Get clean readable text with linked timestamps
python3 '{baseDir}/scripts/fetch_transcript.py' 'YOUTUBE_URL' --format text

# Get raw SRT
python3 '{baseDir}/scripts/fetch_transcript.py' 'YOUTUBE_URL' --format srt

# Specify languages (priority order)
python3 '{baseDir}/scripts/fetch_transcript.py' 'YOUTUBE_URL' --langs 'zh,en,ja'

# List available subtitle languages
python3 '{baseDir}/scripts/fetch_transcript.py' 'YOUTUBE_URL' --list

# Force re-fetch (ignore cache)
python3 '{baseDir}/scripts/fetch_transcript.py' 'YOUTUBE_URL' --refresh
```

**Important:** Always single-quote YouTube URLs — zsh treats `?` as a glob wildcard.

### What the Script Does

1. **Fetches metadata** via `yt-dlp --dump-json` — title, channel, duration, chapters, tags, description
2. **Downloads subtitles** — tries manual subs first, falls back to auto-generated
3. **Parses SRT** — strips HTML tags, alignment codes, sequence numbers
4. **Deduplicates** — removes consecutive duplicate lines (common in auto-generated subs)
5. **Segments into sentences** — splits at punctuation boundaries, merges fragments across subtitle blocks, allocates timestamps proportionally (CJK-aware)
6. **Caches** to `youtube-workspace/{channel}/{title}-{id}/` for reuse
7. **Outputs** structured JSON with metadata + clean sentences

### JSON Output Structure

```json
{
  "video_id": "nr33urYfVXM",
  "title": "Prusa Core One L Review",
  "channel": "Made with Layers",
  "duration": 1423,
  "upload_date": "2025-06-10",
  "url": "https://www.youtube.com/watch?v=nr33urYfVXM",
  "description": "...",
  "chapters": [
    {"title": "Introduction", "start": 0, "end": 45},
    {"title": "Specifications", "start": 45, "end": 180}
  ],
  "tags": ["3d printing", "prusa"],
  "transcript_language": "en",
  "is_auto_generated": true,
  "sentences": [
    {"text": "Welcome to the review.", "start": "00:00:01", "end": "00:00:04"},
    {"text": "Today we're looking at the Prusa Core One L.", "start": "00:00:04", "end": "00:00:08"}
  ]
}
```

### Accepted URL Formats

| Format | Example |
|--------|---------|
| Standard | `https://www.youtube.com/watch?v=dQw4w9WgXcQ` |
| Short | `https://youtu.be/dQw4w9WgXcQ` |
| Embed | `https://www.youtube.com/embed/dQw4w9WgXcQ` |
| Shorts | `https://www.youtube.com/shorts/dQw4w9WgXcQ` |
| Bare ID | `dQw4w9WgXcQ` |

### Handling Long Transcripts

Videos over 30 minutes can produce transcripts that are too large to analyze in a single pass. When the JSON output has more than ~300 sentences:

1. Use the chapter data to process sections independently
2. Summarize each chapter separately, then synthesize
3. For specific questions ("what does it say about X"), search the sentences for relevant sections rather than reading the entire transcript

## Timestamp Linking

Every timestamp in the output must be a clickable markdown link that jumps to that moment in the video. Bare timestamps like `[00:15]` are useless — readers need to click through to the video.

### Format

```
[MM:SS](https://www.youtube.com/watch?v={VIDEO_ID}&t={TOTAL_SECONDS}s)
```

Convert `HH:MM:SS` → total seconds: `hours*3600 + minutes*60 + seconds`

| Display | Seconds | Markdown |
|---------|---------|----------|
| 00:15 | 15 | `[00:15](https://www.youtube.com/watch?v=abc123&t=15s)` |
| 01:22 | 82 | `[01:22](https://www.youtube.com/watch?v=abc123&t=82s)` |
| 05:21 | 321 | `[05:21](https://www.youtube.com/watch?v=abc123&t=321s)` |
| 1:02:30 | 3750 | `[1:02:30](https://www.youtube.com/watch?v=abc123&t=3750s)` |

Place timestamp links inline at the end of each point as a citation. Include the full video URL at the end of the output for reference.

### Full Output Example

Given: `"https://www.youtube.com/watch?v=nr33urYfVXM list the topics of this video"`

---

The video provides an in-depth review of the Prusa Core One L, a large-format CoreXY 3D printer. Below are the primary topics covered:

**1. Printer Specifications & Features**

- **Physical Specs:** Discussion of the $1,999 price point, the 300x300x330mm build volume, and the all-steel exoskeleton frame [00:15](https://www.youtube.com/watch?v=nr33urYfVXM&t=15s).
- **Heating System:** Details on the upgraded AC heated bed (reaches 120°C in 5 minutes) and the 60°C heated chamber enabled by dual circulation fans [00:39](https://www.youtube.com/watch?v=nr33urYfVXM&t=39s).
- **Extruder & Cooling:** Overview of the Nextruder with a 10:1 gearbox, 290°C max nozzle temperature, and the 360°C cooling system [01:22](https://www.youtube.com/watch?v=nr33urYfVXM&t=82s).

**2. Setup and Connectivity**

- **Unboxing:** The thoughtful "slide-out" box design and the fact that the machine comes fully assembled [04:10](https://www.youtube.com/watch?v=nr33urYfVXM&t=250s).
- **Software Integration:** Setting up Wi-Fi, using the Prusa Connect cloud service for multi-printer management, and updating firmware remotely [05:21](https://www.youtube.com/watch?v=nr33urYfVXM&t=321s).
- **Automation:** Demonstration of the automatic vent design that opens or closes based on the filament type [07:04](https://www.youtube.com/watch?v=nr33urYfVXM&t=424s).

**3. Performance Benchmarks**

- **Speed & Quality Tests:** Printing a "Benchy" in 42 minutes and running tolerance tests that achieved perfect scores down to 0.05 mm [08:53](https://www.youtube.com/watch?v=nr33urYfVXM&t=533s).
- **Surface Quality Comparison:** Side-by-side comparisons with the Prusa XL, Bamboo Lab A1, and Creality K2 Pro [12:25](https://www.youtube.com/watch?v=nr33urYfVXM&t=745s).

For more details, watch the full review: https://www.youtube.com/watch?v=nr33urYfVXM

---

## Phase 2: Analyze

Choose analysis modules based on what the user needs. Not every video requires every analysis — match the depth to the request.

### Intent Detection

| User Says | Analysis to Apply |
|-----------|-------------------|
| "summarize this video" | Summary |
| "what are the key points" | Summary + Key Points |
| "list the topics" | Topic Extraction |
| "who's speaking" / interview / podcast | Speaker Identification |
| "what does X say about Y" | Topic Extraction + targeted search |
| "any good quotes" | Quote Extraction |
| "is this accurate" / "fact check" | Fact-Check Flagging |
| "compare these videos" | Comparative Analysis |
| "I'm researching X" | Full Analysis (Summary + Topics + Key Points + Quotes) |
| "what should I do based on this" | Action Items |
| "help me write about this" | Summary + Quotes + Structure Breakdown |

When intent is ambiguous, default to **Summary + Key Points**.

### Summary

```markdown
## Summary: {Video Title}

**Channel:** {channel} | **Duration:** {duration} | **Published:** {date}

### Executive Summary
{2-3 sentences — core message and why it matters}

### Key Points
1. {Point with detail} [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns)
2. {Point with detail} [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns)
3. {Point with detail} [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns)

### Takeaways
- {Actionable insight}
```

For long videos (>30 min), segment by chapters. For short videos (<10 min), keep concise.

### Speaker Identification

For interviews, podcasts, panels:

1. **Identify speakers** from metadata — channel name = host, title often names guest, description may list participants
2. **Detect turns** from conversational patterns — questions vs. answers, topic changes
3. **Label with timestamps:**

```markdown
**Host (Channel Name):** Opening question... [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns)

**Guest (Guest Name):** Response... [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns)
```

### Topic Extraction

```markdown
### Topics
- **{Topic 1}** — {brief description} [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns)
- **{Topic 2}** — {brief description} [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns)

### Tags
`tag1` `tag2` `tag3` `tag4` `tag5`
```

### Content Structure Breakdown

```markdown
### Structure
| Section | Timestamp | Purpose |
|---------|-----------|---------|
| Hook | [0:00](https://www.youtube.com/watch?v=ID&t=0s) | {What draws the viewer in} |
| Main Point 1 | [2:30](https://www.youtube.com/watch?v=ID&t=150s) | {Topic and approach} |
| Conclusion | [14:00](https://www.youtube.com/watch?v=ID&t=840s) | {Wrap-up and CTA} |
```

### Quote Extraction

```markdown
### Notable Quotes

> "The exact quote from the transcript."
> — {Speaker}, [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns)
```

Focus on statements that are insightful, surprising, or represent a core argument.

### Fact-Check Flagging

```markdown
### Claims to Verify
| Claim | Timestamp | Why Flag |
|-------|-----------|----------|
| "{claim}" | [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns) | {Statistical / Historical / Unattributed} |
```

### Action Items

```markdown
### Action Items
1. **{Action}** — {Context} [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns)
2. **{Action}** — {Context} [MM:SS](https://www.youtube.com/watch?v=ID&t=Ns)
```

### Sentiment & Tone

```markdown
### Tone
**Overall:** {Educational / Persuasive / Casual / Critical / Inspirational / Technical}
**Emotional Arc:** {e.g., "Opens with urgency, shifts to optimism, closes with a call to action"}
```

### Comparative Analysis

When analyzing multiple videos on the same topic:

```markdown
## Comparison: {Topic}

| Aspect | Video 1: {Title} | Video 2: {Title} |
|--------|-------------------|-------------------|
| Core Argument | {summary} | {summary} |
| Key Evidence | {what they cite} | {what they cite} |
| Tone | {tone} | {tone} |
| Gaps | {what's missing} | {what's missing} |

### Points of Agreement
- {shared conclusions}

### Points of Disagreement
- {where they differ and why}

### Synthesis
{What a viewer gains from watching both that they wouldn't get from either alone}
```

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| "Video unavailable" | Deleted, private, or region-locked | Inform user — no workaround |
| "No subtitles found" | Transcripts disabled | Run with `--list` to check; if none exist, inform user |
| "Sign in to confirm your age" | Age-restricted | Set env: `YOUTUBE_TRANSCRIPT_COOKIES_FROM_BROWSER=chrome` |
| "HTTP Error 429" | Rate limited | Wait a few minutes, retry |
| "yt-dlp is not installed" | Missing dependency | Show install command for user's platform |
| Garbled auto-generated text | Poor auto-transcription | Note in output that transcript is auto-generated and may contain errors |

## Common Mistakes

- **Using bare timestamps without links** — every `[MM:SS]` must link to `youtube.com/watch?v=ID&t=Ns` so readers can click through to that moment
- **Loading raw yt-dlp JSON into context** — the `--dump-json` output is thousands of lines; use the script which extracts only relevant fields
- **Dumping raw SRT without cleaning** — use the script; it handles HTML stripping, dedup, and sentence segmentation
- Running full analysis when the user only asked for a quick summary
- Forgetting to single-quote URLs in shell commands (zsh glob issue)
- Not checking for cached data before re-downloading
- Treating auto-generated transcripts as perfectly accurate
- Ignoring chapter data when it's available for structuring the output

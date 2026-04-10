#!/usr/bin/env python3
"""
YouTube transcript fetcher and cleaner.

Downloads video metadata and subtitles via yt-dlp, parses subtitle files into
clean sentence-segmented text with timestamps, and outputs structured JSON.

Usage:
    python fetch_transcript.py <url-or-id> [options]

Options:
    --langs LANGS       Comma-separated language codes in priority order (default: en)
    --format FORMAT     Output format: json, text, srt (default: json)
    --output-dir DIR    Base output directory (default: youtube-workspace)
    --refresh           Force re-fetch, ignore cache
    --list              List available subtitle languages
    --no-cache          Skip caching, print to stdout only

Outputs (json format):
    {
        "video_id": "...",
        "title": "...",
        "channel": "...",
        "duration": 1234,
        "upload_date": "2025-01-15",
        "url": "https://www.youtube.com/watch?v=...",
        "description": "...",
        "chapters": [...],
        "tags": [...],
        "thumbnail": "...",
        "transcript_language": "en",
        "is_auto_generated": true,
        "sentences": [
            {"text": "...", "start": "00:00:15", "end": "00:00:22"},
            ...
        ]
    }
"""

import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path


# --- URL / ID parsing ---

VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?.*v=|embed/|shorts/|live/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)
BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(url_or_id: str) -> str:
    m = VIDEO_ID_RE.search(url_or_id)
    if m:
        return m.group(1)
    if BARE_ID_RE.match(url_or_id.strip()):
        return url_or_id.strip()
    raise ValueError(f"Cannot extract video ID from: {url_or_id}")


# --- Slug generation ---

def slugify(text: str, max_len: int = 80) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:max_len]


# --- yt-dlp interaction ---

def check_ytdlp() -> bool:
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def ensure_ytdlp() -> bool:
    """Check for yt-dlp and auto-install via pip if missing."""
    if check_ytdlp():
        return True

    print("yt-dlp not found. Installing via pip...", file=sys.stderr)
    for cmd in [
        [sys.executable, "-m", "pip", "install", "--quiet", "yt-dlp"],
        ["pip3", "install", "--quiet", "yt-dlp"],
        ["pip", "install", "--quiet", "yt-dlp"],
    ]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and check_ytdlp():
                print("yt-dlp installed successfully.", file=sys.stderr)
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    return False


def fetch_metadata(video_id: str) -> dict:
    """Fetch video metadata via yt-dlp --dump-json, extracting only needed fields."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", url],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)

    chapters = []
    for ch in (data.get("chapters") or []):
        chapters.append({
            "title": ch.get("title", ""),
            "start": ch.get("start_time", 0),
            "end": ch.get("end_time", 0),
        })

    # If no chapters in metadata, try parsing from description
    if not chapters:
        chapters = parse_chapters_from_description(
            data.get("description", ""),
            data.get("duration", 0)
        )

    return {
        "video_id": video_id,
        "title": data.get("title", ""),
        "channel": data.get("channel", data.get("uploader", "")),
        "duration": data.get("duration", 0),
        "upload_date": format_date(data.get("upload_date", "")),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "description": data.get("description", ""),
        "chapters": chapters,
        "tags": data.get("tags", []),
        "thumbnail": data.get("thumbnail", ""),
        "view_count": data.get("view_count"),
        "like_count": data.get("like_count"),
    }


def format_date(raw: str) -> str:
    if raw and len(raw) == 8:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw


def parse_chapters_from_description(description: str, duration: int) -> list:
    chapters = []
    for line in description.split("\n"):
        m = re.match(r"^\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s+(.+)$", line.strip())
        if m:
            hours = int(m.group(1) or 0)
            start = hours * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            chapters.append({"title": m.group(4).strip(), "start": start})

    if len(chapters) < 2:
        return []

    result = []
    for i, ch in enumerate(chapters):
        end = chapters[i + 1]["start"] if i < len(chapters) - 1 else max(duration, ch["start"])
        result.append({"title": ch["title"], "start": ch["start"], "end": end})
    return result


def download_subtitles(video_id: str, langs: list[str], output_dir: Path) -> tuple[Path | None, bool, str]:
    """Download subtitles, returns (sub_path, is_auto_generated, format).

    Prefers auto-generated json3 format (YouTube's native caption format)
    because it provides clean, non-overlapping text segments. Manual subs
    uploaded by creators are sometimes just re-uploaded auto-generated text
    with progressive-overlap artifacts baked in. json3 auto-subs avoid this.

    Fallback order: auto json3 → manual json3 → manual SRT → auto SRT.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    lang_str = ",".join(langs)

    # Prefer auto-generated json3 — cleanest format, no overlap artifacts
    subprocess.run(
        [
            "yt-dlp", "--write-auto-subs", "--sub-langs", lang_str,
            "--sub-format", "json3", "--skip-download",
            "-o", str(output_dir / "auto"), url,
        ],
        capture_output=True, text=True, timeout=60
    )

    for lang in langs:
        json3_path = output_dir / f"auto.{lang}.json3"
        if json3_path.exists() and json3_path.stat().st_size > 0:
            return json3_path, True, "json3"

    # Try manual subs in json3
    subprocess.run(
        [
            "yt-dlp", "--write-subs", "--sub-langs", lang_str,
            "--sub-format", "json3", "--skip-download",
            "-o", str(output_dir / "manual"), url,
        ],
        capture_output=True, text=True, timeout=60
    )

    for lang in langs:
        json3_path = output_dir / f"manual.{lang}.json3"
        if json3_path.exists() and json3_path.stat().st_size > 0:
            return json3_path, False, "json3"

    # Fall back to manual SRT
    subprocess.run(
        [
            "yt-dlp", "--write-subs", "--sub-langs", lang_str,
            "--skip-download", "--convert-subs", "srt",
            "-o", str(output_dir / "manual"), url,
        ],
        capture_output=True, text=True, timeout=60
    )

    for lang in langs:
        srt_path = output_dir / f"manual.{lang}.srt"
        if srt_path.exists() and srt_path.stat().st_size > 0:
            return srt_path, False, "srt"

    return None, False, ""


def list_subtitles(video_id: str) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    proc = subprocess.run(
        ["yt-dlp", "--list-subs", url],
        capture_output=True, text=True, timeout=30
    )
    return proc.stdout + proc.stderr


def download_thumbnail(video_id: str, output_dir: Path) -> str | None:
    url = f"https://www.youtube.com/watch?v={video_id}"
    subprocess.run(
        [
            "yt-dlp", "--write-thumbnail", "--skip-download",
            "-o", str(output_dir / "thumbnail"), url,
        ],
        capture_output=True, text=True, timeout=30
    )
    # Find the thumbnail file (could be .webp, .jpg, .png)
    for ext in ["webp", "jpg", "png"]:
        thumb = output_dir / f"thumbnail.{ext}"
        if thumb.exists():
            return str(thumb)
    return None


# --- SRT parsing and cleaning ---

TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
ALIGNMENT_RE = re.compile(r"\{\\an\d\}")
SENTENCE_END_RE = re.compile(r"[.?!…。？！]$")


def parse_json3(json3_text: str) -> list[dict]:
    """Parse YouTube json3 caption format into clean snippets.

    json3 is YouTube's native caption format. Each event has a start time
    and segments with individual words/phrases, avoiding the progressive
    overlap artifacts found in auto-generated SRT.
    """
    data = json.loads(json3_text)
    events = data.get("events", [])
    snippets = []

    for event in events:
        segs = event.get("segs")
        if not segs:
            continue

        # Merge segment text
        parts = []
        for seg in segs:
            text = seg.get("utf8", "").replace("\n", " ").strip()
            if text:
                parts.append(text)

        merged = " ".join(parts).strip()
        merged = HTML_TAG_RE.sub("", merged)
        merged = re.sub(r"\s+", " ", merged).strip()

        if not merged:
            continue

        start_ms = event.get("tStartMs", 0)
        dur_ms = event.get("dDurationMs", 0)
        start = start_ms / 1000
        end = (start_ms + dur_ms) / 1000

        snippets.append({"text": merged, "start": start, "end": end})

    return snippets


def parse_srt(srt_text: str) -> list[dict]:
    """Parse SRT into list of {text, start, end} snippets."""
    blocks = re.split(r"\n\n+", srt_text.strip())
    snippets = []

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        # Find timestamp line
        ts_match = None
        text_start_idx = 0
        for i, line in enumerate(lines):
            ts_match = TIMESTAMP_RE.search(line)
            if ts_match:
                text_start_idx = i + 1
                break

        if not ts_match or text_start_idx >= len(lines):
            continue

        start = (
            int(ts_match.group(1)) * 3600
            + int(ts_match.group(2)) * 60
            + int(ts_match.group(3))
            + int(ts_match.group(4)) / 1000
        )
        end = (
            int(ts_match.group(5)) * 3600
            + int(ts_match.group(6)) * 60
            + int(ts_match.group(7))
            + int(ts_match.group(8)) / 1000
        )

        # Join text lines, strip HTML and alignment tags
        text = " ".join(lines[text_start_idx:])
        text = HTML_TAG_RE.sub("", text)
        text = ALIGNMENT_RE.sub("", text)
        text = text.strip()

        if text:
            snippets.append({"text": text, "start": start, "end": end})

    return snippets


def is_cjk(char: str) -> bool:
    cp = ord(char)
    return (
        (0x4E00 <= cp <= 0x9FFF)
        or (0x3040 <= cp <= 0x309F)
        or (0x30A0 <= cp <= 0x30FF)
        or (0xAC00 <= cp <= 0xD7AF)
        or (0x3400 <= cp <= 0x4DBF)
    )


def merge_text(a: str, b: str) -> str:
    """Merge two text fragments, handling CJK (no space) vs Latin (space needed)."""
    if not a:
        return b
    if not b:
        return a
    if is_cjk(a[-1]) or is_cjk(b[0]):
        return a + b
    return a.rstrip() + " " + b.lstrip()


def clean_repeated_phrases(text: str) -> str:
    """Remove repeated phrases within a single subtitle line.

    Auto-generated subs often produce progressive text like:
    "Today I will test Today I will test Today I will test the printer."
    This detects and removes the repeated prefix fragments.
    """
    words = text.split()
    n = len(words)
    if n < 4:
        return text

    # Try chunk sizes from large to small — find the longest repeated prefix
    for chunk_size in range(n // 2, 1, -1):
        chunk = words[:chunk_size]
        chunk_str = " ".join(chunk)
        # Count how many times this chunk appears consecutively at the start
        repeats = 0
        pos = 0
        remaining = text
        while remaining.startswith(chunk_str):
            repeats += 1
            pos += len(chunk_str)
            remaining = remaining[len(chunk_str):].lstrip()

        if repeats >= 2:
            # Keep one copy of the chunk + whatever follows
            return chunk_str + " " + remaining if remaining else chunk_str

    return text


def deduplicate_snippets(snippets: list[dict]) -> list[dict]:
    """Remove repeated text from auto-generated subtitle artifacts.

    Handles:
    1. Repeated phrases within a single line (progressive auto-captions)
    2. Consecutive duplicate lines
    3. Lines where the previous text is a prefix of the current (overlap)
    """
    if not snippets:
        return []

    # Step 1: Clean intra-line repetition
    for s in snippets:
        s["text"] = clean_repeated_phrases(s["text"])

    # Step 2: Remove consecutive duplicates and overlapping prefixes
    result = [snippets[0]]
    for s in snippets[1:]:
        prev_text = result[-1]["text"]
        curr_text = s["text"]

        # Exact duplicate
        if curr_text == prev_text:
            result[-1]["end"] = max(result[-1]["end"], s["end"])
            continue

        # Current starts with previous text (overlap from progressive captions)
        if curr_text.startswith(prev_text):
            result[-1]["text"] = curr_text
            result[-1]["end"] = s["end"]
            continue

        # Previous ends with the start of current (cross-boundary overlap)
        overlap = False
        min_overlap = min(len(prev_text), len(curr_text)) // 2
        for i in range(min_overlap, 3, -1):
            if prev_text.endswith(curr_text[:i]):
                s["text"] = curr_text[i:].lstrip()
                if s["text"]:
                    result.append(s)
                overlap = True
                break

        if not overlap:
            result.append(s)

    return [s for s in result if s["text"].strip()]


def segment_into_sentences(snippets: list[dict]) -> list[dict]:
    """
    Merge subtitle fragments into natural sentences.
    Splits at sentence-ending punctuation, merges across snippet boundaries,
    and allocates timestamps proportionally by character length.
    """
    if not snippets:
        return []

    # First, build a stream of text fragments with timing
    fragments = []
    for s in snippets:
        text = s["text"]
        # Split at sentence boundaries within a single snippet
        parts = re.split(r"(?<=[.?!…。？！])\s+", text)
        if len(parts) <= 1:
            fragments.append({"text": text, "start": s["start"], "end": s["end"]})
        else:
            duration = s["end"] - s["start"]
            total_len = sum(len(p) for p in parts)
            offset = s["start"]
            for p in parts:
                if not p.strip():
                    continue
                frac = len(p) / total_len if total_len > 0 else 1
                frag_dur = duration * frac
                fragments.append({"text": p.strip(), "start": offset, "end": offset + frag_dur})
                offset += frag_dur

    # Now merge fragments into sentences
    sentences = []
    buffer_text = ""
    buffer_start = 0.0
    buffer_end = 0.0

    for frag in fragments:
        if not buffer_text:
            buffer_start = frag["start"]

        buffer_text = merge_text(buffer_text, frag["text"])
        buffer_end = frag["end"]

        if SENTENCE_END_RE.search(buffer_text):
            sentences.append({
                "text": buffer_text.strip(),
                "start": format_timestamp(buffer_start),
                "end": format_timestamp(buffer_end),
            })
            buffer_text = ""

    # Flush remaining
    if buffer_text.strip():
        sentences.append({
            "text": buffer_text.strip(),
            "start": format_timestamp(buffer_start),
            "end": format_timestamp(buffer_end),
        })

    return sentences


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def timestamp_to_seconds(ts: str) -> int:
    parts = ts.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def format_display_timestamp(seconds: int) -> str:
    """Format seconds as MM:SS or H:MM:SS for display."""
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h}:{m:02d}:{s:02d}"
    else:
        m = seconds // 60
        s = seconds % 60
        return f"{m:02d}:{s:02d}"


# --- Output formatting ---

def format_text_output(meta: dict, sentences: list[dict], is_auto: bool) -> str:
    """Format as clean readable text with timestamps."""
    lines = []
    lines.append(f"# {meta['title']}")
    lines.append(f"")
    lines.append(f"**Channel:** {meta['channel']} | **Duration:** {format_duration(meta['duration'])} | **Published:** {meta['upload_date']}")
    if is_auto:
        lines.append(f"*Note: Transcript is auto-generated and may contain errors.*")
    lines.append("")

    if meta["chapters"]:
        # Group sentences by chapter
        for ch in meta["chapters"]:
            secs = ch["start"]
            display = format_display_timestamp(secs)
            lines.append(f"## [{display}](https://www.youtube.com/watch?v={meta['video_id']}&t={secs}s) {ch['title']}")
            lines.append("")
            ch_sentences = [
                s for s in sentences
                if timestamp_to_seconds(s["start"]) >= ch["start"]
                and timestamp_to_seconds(s["start"]) < ch["end"]
            ]
            # Group into paragraphs (3-5 sentences each)
            para = []
            for s in ch_sentences:
                para.append(s["text"])
                if len(para) >= 4:
                    secs = timestamp_to_seconds(s["start"])
                    display = format_display_timestamp(secs)
                    lines.append(" ".join(para) + f" [{display}](https://www.youtube.com/watch?v={meta['video_id']}&t={secs}s)")
                    lines.append("")
                    para = []
            if para:
                last = ch_sentences[-1] if ch_sentences else None
                if last:
                    secs = timestamp_to_seconds(last["start"])
                    display = format_display_timestamp(secs)
                    lines.append(" ".join(para) + f" [{display}](https://www.youtube.com/watch?v={meta['video_id']}&t={secs}s)")
                else:
                    lines.append(" ".join(para))
                lines.append("")
    else:
        # No chapters — group into paragraphs
        para = []
        for s in sentences:
            para.append(s["text"])
            if len(para) >= 4:
                secs = timestamp_to_seconds(s["start"])
                display = format_display_timestamp(secs)
                lines.append(" ".join(para) + f" [{display}](https://www.youtube.com/watch?v={meta['video_id']}&t={secs}s)")
                lines.append("")
                para = []
        if para:
            secs = timestamp_to_seconds(sentences[-1]["start"]) if sentences else 0
            display = format_display_timestamp(secs)
            lines.append(" ".join(para) + f" [{display}](https://www.youtube.com/watch?v={meta['video_id']}&t={secs}s)")
            lines.append("")

    return "\n".join(lines)


def format_duration(seconds: int) -> str:
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h}:{m:02d}:{s:02d}"
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"


# --- Cache management ---

def get_cache_dir(video_id: str, meta: dict, base_dir: Path) -> Path:
    channel_slug = slugify(meta.get("channel", "unknown"))
    title_slug = slugify(meta.get("title", video_id))
    return base_dir / channel_slug / f"{title_slug}-{video_id}"


def is_cached(cache_dir: Path) -> bool:
    return (
        (cache_dir / "metadata.json").exists()
        and (cache_dir / "transcript.json").exists()
    )


# --- Main ---

def main():
    import argparse

    parser = argparse.ArgumentParser(description="YouTube transcript fetcher")
    parser.add_argument("url", help="YouTube URL or video ID")
    parser.add_argument("--langs", default="en", help="Comma-separated language codes (default: en)")
    parser.add_argument("--format", choices=["json", "text", "srt"], default="json", help="Output format")
    parser.add_argument("--output-dir", default="youtube-workspace", help="Base output directory")
    parser.add_argument("--refresh", action="store_true", help="Force re-fetch")
    parser.add_argument("--list", action="store_true", help="List available subtitle languages")
    parser.add_argument("--no-cache", action="store_true", help="Skip caching, stdout only")

    args = parser.parse_args()

    # Check yt-dlp, auto-install if missing
    if not ensure_ytdlp():
        print("Error: yt-dlp is not installed and auto-install failed.", file=sys.stderr)
        print("Install manually with: pip install yt-dlp", file=sys.stderr)
        sys.exit(1)

    video_id = extract_video_id(args.url)
    langs = [l.strip() for l in args.langs.split(",")]

    # List mode
    if args.list:
        print(list_subtitles(video_id))
        sys.exit(0)

    base_dir = Path(args.output_dir)

    # Check cache
    meta = None
    if not args.refresh and not args.no_cache:
        # Quick check by video ID in any subdirectory
        for p in base_dir.rglob("metadata.json"):
            try:
                m = json.loads(p.read_text())
                if m.get("video_id") == video_id:
                    cache_dir = p.parent
                    if (cache_dir / "transcript.json").exists():
                        transcript_data = json.loads((cache_dir / "transcript.json").read_text())
                        if args.format == "json":
                            print(json.dumps({**m, **transcript_data}, indent=2))
                        elif args.format == "text":
                            print(format_text_output(m, transcript_data["sentences"], transcript_data.get("is_auto_generated", False)))
                        elif args.format == "srt":
                            if (cache_dir / "transcript.srt").exists():
                                print((cache_dir / "transcript.srt").read_text())
                            else:
                                print("SRT file not cached.", file=sys.stderr)
                                sys.exit(1)
                        sys.exit(0)
            except (json.JSONDecodeError, KeyError):
                continue

    # Fetch metadata
    print(f"Fetching metadata for {video_id}...", file=sys.stderr)
    meta = fetch_metadata(video_id)

    cache_dir = get_cache_dir(video_id, meta, base_dir)

    # Download subtitles
    print(f"Downloading subtitles ({','.join(langs)})...", file=sys.stderr)
    tmp_dir = cache_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    sub_path, is_auto, sub_format = download_subtitles(video_id, langs, tmp_dir)

    if not sub_path:
        print(f"Error: No subtitles found for languages: {', '.join(langs)}", file=sys.stderr)
        print("Run with --list to see available languages.", file=sys.stderr)
        sys.exit(1)

    # Detect which language was downloaded
    transcript_lang = "unknown"
    for lang in langs:
        if f".{lang}." in sub_path.name:
            transcript_lang = lang
            break

    # Parse and clean
    print(f"Parsing and cleaning transcript ({sub_format})...", file=sys.stderr)
    raw_text = sub_path.read_text(encoding="utf-8", errors="replace")

    if sub_format == "json3":
        snippets = parse_json3(raw_text)
    else:
        snippets = parse_srt(raw_text)

    snippets = deduplicate_snippets(snippets)
    sentences = segment_into_sentences(snippets)

    transcript_data = {
        "transcript_language": transcript_lang,
        "is_auto_generated": is_auto,
        "sentences": sentences,
    }

    # Cache results
    if not args.no_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        (cache_dir / "transcript.json").write_text(json.dumps(transcript_data, indent=2, ensure_ascii=False))

        # Keep raw subtitle file
        cached_sub = cache_dir / f"transcript.{sub_format}"
        if sub_path.exists():
            cached_sub.write_text(raw_text)

        # Download thumbnail
        download_thumbnail(video_id, cache_dir)

        # Clean up tmp
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

        print(f"Cached to: {cache_dir}", file=sys.stderr)

    # Output
    output = {**meta, **transcript_data}

    if args.format == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.format == "text":
        print(format_text_output(meta, sentences, is_auto))
    elif args.format == "srt":
        print(raw_text)


if __name__ == "__main__":
    main()

---
name: video-frames
description: Extract frames or short clips from videos using ffmpeg. Use when the user asks to grab a frame, create a thumbnail, extract a screenshot from a video, or inspect a specific moment in a video file.
display_name: Video Frames
version: "1.0.0"
author: Astralform
---

# Video Frames (ffmpeg)

Extract single frames from video files for inspection, thumbnails, or analysis.

## Prerequisites

Requires `ffmpeg` installed on the system:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
apt-get install ffmpeg
```

## Extract a Frame

### First frame

```bash
ffmpeg -hide_banner -loglevel error -i /path/to/video.mp4 -frames:v 1 /tmp/frame.jpg
```

### At a specific timestamp

```bash
ffmpeg -hide_banner -loglevel error -ss 00:00:10 -i /path/to/video.mp4 -frames:v 1 /tmp/frame-10s.jpg
```

### At a specific frame index

```bash
ffmpeg -hide_banner -loglevel error -i /path/to/video.mp4 -vf "select=eq(n\,42)" -frames:v 1 /tmp/frame-42.jpg
```

## Extract Multiple Frames

### One frame per second

```bash
ffmpeg -hide_banner -loglevel error -i /path/to/video.mp4 -vf fps=1 /tmp/frames_%04d.jpg
```

### Every N seconds

```bash
ffmpeg -hide_banner -loglevel error -i /path/to/video.mp4 -vf "fps=1/5" /tmp/frames_%04d.jpg
```

### Key frames only (scene changes)

```bash
ffmpeg -hide_banner -loglevel error -i /path/to/video.mp4 -vf "select=eq(pict_type\,I)" -vsync vfr /tmp/keyframe_%04d.jpg
```

## Extract a Short Clip

### 5-second clip starting at 30s

```bash
ffmpeg -hide_banner -loglevel error -ss 00:00:30 -i /path/to/video.mp4 -t 5 -c copy /tmp/clip.mp4
```

## Tips

- Use `-ss` **before** `-i` for fast seeking (input seeking), or after `-i` for precise seeking (output seeking).
- Use `.jpg` for quick sharing, `.png` for crisp/lossless frames.
- Add `-q:v 2` for higher JPEG quality (range 2-31, lower is better).
- Add `-vf scale=1280:-1` to resize output frames.
- Use `-hide_banner -loglevel error` to suppress noisy ffmpeg output.

## Video Info

Get video metadata (duration, resolution, codec, fps):

```bash
ffprobe -hide_banner -v error -show_entries format=duration -show_entries stream=width,height,r_frame_rate,codec_name -of json /path/to/video.mp4
```

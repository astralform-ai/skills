# Publishing copy

Four text deliverables ship with the video: `youtube.md`, `bilibili.md`,
`blog.md`, and one social post. Section order is fixed; the content is written
fresh each episode in the user's own voice.

Promotional slots — membership, sponsor, community, socials — are
**placeholders, not requirements**. Fill them from context or memory when the
user has them, and drop the block entirely when they do not. Never invent a
sponsor or a community link.

## youtube.md

```
## Title (candidates)
«2–3 options»

## Description
«membership / channel promo»      ← omit if none
«who you are, where else to find you»
«the actual description»
«related links»                   ← source material, previous episode, repo, playlist

## Chapters
0:00 «opening»
m:ss «section»
```

**Titles.** Offer two or three, all consistent with how the series already
speaks. Hooks that work: a concrete number, the series' position on something,
or the thing you only discovered by actually doing it. Avoid a hook the video
does not deliver — it costs more in retention than it gains in clicks.

**Chapters** come from the scene plan, which already came from the SRT, so they
land on real transitions. Merge scenes that belong to one argument; a chapter
list should describe the structure, not mirror the cut list. YouTube needs the
first chapter at `0:00` and at least three chapters.

```python
import json
for sc in json.load(open("ep/plan.json"))["scenes"]:
    m, sec = divmod(int(sc["start"]), 60)
    print(f"{m}:{sec:02d} {sc.get('headline', '')}")
```

## bilibili.md

Same title and description; leaner, and **the sponsor line goes first**. No
chapter list.

```
## Title (candidates)
## Description
«sponsor»
«who you are»
«the actual description»
«related links»
```

## blog.md

A companion post, not a transcript. It can go deeper than the video: the
sources, the thing that did not fit, the caveat.

```yaml
---
title: "..."          # carries a hook
date: "YYYY-MM-DD"
excerpt: "..."
tags: [...]           # canonical tags only — not three synonyms for one idea
lang: "zh"
cover: "blog-images/blog-cover.png"
---
```

Illustrate it with frames from the video, so the post and the video look like
one release:

```python
run("mkdir -p ep/blog-images && ffmpeg -y -ss 42 -i ep/renders/episode.mp4 "
    "-frames:v 1 ep/blog-images/fig-01.png")
```

## The social post

One post, scannable in three seconds:

- a first line that is a hook, not a summary;
- the key points as arrows or numbers;
- the link to the source or the video.

## Voice

All four inherit the user's writing style — from the conversation, from memory,
or from a style skill if one is loaded. If you have nothing to go on, ask for a
previous episode's description and match it. Do not default to launch-announcement
enthusiasm; it reads as generic and dates badly.

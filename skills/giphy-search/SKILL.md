---
name: giphy-search
description: Search Giphy for GIFs and return URLs. Use when the user asks for a GIF, reaction image, meme, or when a visual reaction (celebration, humor, emotion) would enhance the response.
display_name: Giphy Search
version: "1.0.0"
author: Astralform
---

# Giphy Search

Search Giphy for relevant GIFs and return embeddable URLs.

## When to Use

- User explicitly asks for a GIF, meme, or reaction image
- A visual reaction would enhance the conversation (celebration, humor, emotion)
- Keep usage occasional — avoid GIF-only replies or back-to-back GIFs
- Prefer text in serious or information-dense conversations

## API

**Requires:** `GIPHY_API_KEY` environment variable.

### Search Endpoint

```
GET https://api.giphy.com/v1/gifs/search?api_key={GIPHY_API_KEY}&q={query}&limit=1&rating=g&lang=en
```

- URL-encode the query text
- Always use `rating=g` (safe for work)
- `limit=1` for single best match, increase for options

### Response

The GIF URL is at `data[0].images.original.url` (direct GIF) or `data[0].url` (Giphy page link).

## Query Tips

Write queries as short emotional/action phrases:

| Intent | Good Query |
|---|---|
| Excitement | `happy dance` |
| Disappointment | `facepalm reaction` |
| Surprise | `mind blown` |
| Awkward | `awkward silence` |
| Thank you | `thank you bow` |
| Celebration | `celebration confetti` |

## Output

- Return the GIF URL so it can be displayed or embedded
- If no result found, say so and ask for different keywords
- Never send inappropriate or off-topic GIFs

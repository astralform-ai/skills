# Designs

The look of the whole episode is one preset. Pick it in Step 0 and never mix —
a video that changes its palette mid-way reads as broken, not as variety.

Presets live in `{baseDir}/assets/designs.json`. Ask the user to choose; default to
`blockframe`.

| slug | look | good for |
|---|---|---|
| **blockframe** (default) | Neo-brutalist poster — thick ink borders, hard offset shadows, candy accent | High-click-through explainers, product takes |
| `midnight` | Near-black with one luminous accent | Long-form, calm, technical |
| `cobalt-grid` | Editorial parchment + cobalt, structured rules | Data-heavy, journalistic |
| `biennale-yellow` | Warm parchment + sun yellow, indigo ink, hairlines | Friendly, essayistic, culture |
| `forest` | Deep green + cream with coral counterpoint | Reflective, long reads |
| `mono` | Black on white, Swiss grid, red accent | Maximum legibility, zero brand noise |

## Token contract

Every preset defines the same keys, so layouts never special-case a design:

| token | role |
|---|---|
| `bg` / `ink` / `muted` | page, primary text, secondary text |
| `accent` / `accent_ink` | the one highlight colour, and text legible **on** it |
| `panel` | raised surface |
| `border_width` / `hard_shadow` / `corner` | the poster treatment |
| `rule_width` | progress bar and quote rules |
| `kicker_case` / `kicker_tracking` | eyebrow styling |

## Adding a preset

Add an entry to `{baseDir}/assets/designs.json` with all the keys above. No code changes —
the renderer only ever reads tokens. Two rules that keep a preset usable:

- **`accent_ink` must be legible on `accent`.** The chapter card fills the whole
  frame with `accent` and sets type in `accent_ink`; get this wrong and a whole
  scene is unreadable.
- **Keep `accent` punctuation, not filler.** It marks one thing per frame — a
  number, a rule, the progress bar. A frame that is 40% accent has no emphasis
  left to give.

## Colour discipline

- On dark presets, put body text in `ink`/`muted`, never in `accent` — thin
  coloured type on a dark field loses contrast once the platform re-compresses.
- On light presets, text sitting on an `accent` block must be `accent_ink`
  (dark), which stays high-contrast.
- CJK glyphs sit taller in their em box than Latin. The renderer already pads
  accent blocks for this; if you hand-place text on a slab, leave ~0.2em of
  vertical padding or the characters will kiss the edge.

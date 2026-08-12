# Writing a chain that reads as one shot

Six clips joined end to end are not a video. They become one when the prompts
are written as a single continuous move that happens to be cut into
five-second pieces.

## Write the whole list before generating the first segment

The first frame of segment 3 is decided by how you ended segment 2, which is
decided by how you ended segment 1. Writing the prompts one at a time means
discovering at segment 4 that the camera has nowhere left to go.

So plan first. For a 30-second chain at ~5s a segment:

| # | Moves | Comes to rest on |
|---|---|---|
| 1 | camera pushes in from the doorway | the desk, lamp lit, centre frame |
| 2 | hand enters, sets the cup down | the cup, steam rising |
| 3 | camera drifts left along the desk | the open notebook |
| … | | |

The right-hand column is the load-bearing one. It is the literal input to the
next row.

## What goes in a prompt

**Only the motion.** The frame already contains the subject, the lighting, the
lens and the palette — the model is looking at it. Re-describing them competes
with what it can see, and the result is a subject that subtly restyles itself
every five seconds.

Good:

> The camera drifts left along the desk. The steam keeps rising. Motion settles
> on the open notebook.

Bad — every one of these is already in the frame:

> A warm, cinematic shot of a wooden desk in a dim study, a green lamp, a cup of
> coffee, shallow depth of field, 35mm film look. The camera drifts left.

The exception is a **style anchor** of at most one short clause, repeated
verbatim in every segment (`handheld, warm tungsten light`). It costs little and
holds the grade steady. Anything longer starts to fight the frame.

## Ending on a resting beat

The final frame of a segment is the next segment's first frame, and a first
frame is expected to be a still. A segment that ends mid-whip-pan hands the next
one a smear of motion blur to start from, and blur compounds down the chain
faster than anything else.

So end each prompt with a settle: *comes to rest on…*, *slows to a stop*, *holds
on…*. Put the fast motion in the middle of a segment, never at its end.

Cutting the fast motion in half across a seam does not work either — the two
halves are generated independently and will not agree on speed.

## Continuity of things that move on their own

A person walking, a flag, falling rain: each segment restarts that motion from
whatever the frame shows, with no memory of its rhythm. Two consequences worth
planning around:

- **Cyclical motion loses its phase.** A walk cycle will hitch at every seam. If
  a subject must walk for twenty seconds, expect the hitch and frame it wide, or
  choose a motion without a cycle — drifting, falling, pouring, spreading.
- **Anything that leaves the frame is gone.** The next segment cannot bring it
  back; it is not in the frame. Keep what the story needs inside the frame at
  every hand-off point.

## When not to chain

Chaining produces one continuous take. If what the user wants is a sequence of
different shots — a montage, a product from three angles, a story with scene
changes — that is not a chain. Each shot starts from its own still, and they are
joined the same way at the end. Chaining across an intended cut spends four
minutes per segment producing a transition nobody asked for.

Rule of thumb: if you would describe a new location or a new subject in the next
prompt, you want a new still, not the last frame.

## Length before quality collapses

Drift is roughly linear in the number of links, and everything downstream of a
bad frame is worse than it was:

| Links | What to expect |
|---|---|
| 2-3 | indistinguishable from a single take |
| 4-6 | slight exposure and saturation drift; `--match-color` handles it |
| 7-10 | softening and colour shift are visible on a back-to-back compare |
| 11+ | re-anchor instead: a fresh still, and treat the join as a cut |

A minute of genuinely continuous footage from one still is not something this
pipeline delivers well. A minute assembled from three anchored chains of four is.

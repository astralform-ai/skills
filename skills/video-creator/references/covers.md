# Covers

One idea, five aspect ratios: **16:9, 16:10, 4:3, 3:4, 9:16**. Each is laid out
for its own shape. Never crop a 16:9 master down to 9:16 — a title that filled
the frame horizontally becomes three cramped lines with the brand pill sliced
off, and that is exactly what a cheap thumbnail looks like.

```python
# q() is shlex.quote — episode text comes from the user's article/script and
# goes through a shell, so it must be quoted, not hand-wrapped in double quotes.
kicker   = "EP 12"
title    = "音频即时钟"
subtitle = "为什么时间轴不该由感觉决定"
brand    = "ASTRALFORM"
# Repeat --point rather than using the comma-separated --points: episode copy
# routinely contains commas, and they would silently split one point into two.
points   = ["SRT 决定时间轴", "设计只有一套 token", "渲染后逐帧自检"]
pts      = " ".join(f"--point {q(p)}" for p in points)
run(f"python3 {SK}/scripts/make_covers.py --from-plan ep/plan.json "
    f"--kicker {q(kicker)} --title {q(title)} --subtitle {q(subtitle)} "
    f"{pts} --brand {q(brand)} -o ep/covers/")
```

`--from-plan` inherits the video's design and, unless you override them, the
opening scene's headline and body — so the cover and the first frame agree.

## Less, but bigger

A cover is seen at thumbnail size, often on a phone, next to a dozen others. The
title is the whole cover; everything else earns its place or goes.

**Keep:** the title, one line of subtitle, at most 3–4 short points, a small
brand pill.

**Cut, every time:** eyebrow prefixes ("a follow-up to last week's…"), secondary
header lines, footer taglines, and — above all — ratio labels like "16:9" or
"vertical". A label naming the shape of the image adds nothing to a viewer
already looking at it.

If you remove the kicker, do not leave the gap behind: the title block should
re-centre, which `make_covers.py` does automatically because it measures the
stack it is actually drawing.

## Checking them

Look at the 9:16 and 4:3 outputs specifically — they are where an over-long
title first breaks. If the title has wrapped to four lines in portrait, the
title is too long; shorten the words rather than the type size.

Then view each at thumbnail scale, which is how it will really be seen:

```python
# runs in the kernel directly — no shell needed
from PIL import Image
import glob
for p in sorted(glob.glob("ep/covers/*.png")):
    im = Image.open(p); im.thumbnail((320, 320))
    im.save(p.replace(".png", "-thumb.png")); print(p, im.size)
```

If the title is not readable at that size, no amount of polish at full size will
save it.

## Blog cover

The blog post takes a 16:9 cover, saved as `blog-images/blog-cover.png`. Reuse
the video's design so post, video and thumbnail read as one release.

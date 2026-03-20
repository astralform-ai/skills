---
name: ppt-generation
description: Create professional PowerPoint presentations with AI-generated slide images. Use when the user asks to generate, create, or make presentations, slides, pitch decks, or keynotes.
display_name: PPT Generation
version: "1.0.0"
author: Astralform
---

# PPT Generation

Create professional PowerPoint presentations with AI-generated visuals for each slide, maintaining consistent style throughout.

## When to Use

- User asks to create a presentation, PPT, slides, pitch deck, or keynote
- User needs a visually rich presentation (not just text bullets)

## Presentation Styles

| Style | Description | Best For |
|---|---|---|
| **glassmorphism** | Frosted glass panels, blur effects, vibrant gradient backgrounds | Tech products, AI/SaaS, futuristic pitches |
| **dark-premium** | Rich black backgrounds, luminous accents, luxury aesthetic | Premium products, executive presentations |
| **gradient-modern** | Bold mesh gradients, fluid color transitions, contemporary | Startups, creative agencies, brand launches |
| **neo-brutalist** | Raw bold typography, high contrast, anti-design | Edgy brands, Gen-Z, disruptive startups |
| **3d-isometric** | Clean isometric illustrations, floating 3D elements | Tech explainers, product features, SaaS |
| **editorial** | Magazine-quality layouts, sophisticated typography | Annual reports, luxury brands, thought leadership |
| **minimal-swiss** | Grid-based precision, Helvetica-inspired, negative space | Architecture, design firms, consulting |
| **keynote** | Apple-inspired, bold typography, dramatic imagery | Keynotes, product reveals, inspirational talks |

## Workflow

### Step 1: Understand Requirements

Identify from the user:
- **Topic**: What is the presentation about
- **Slide count**: How many slides (default: 5-10)
- **Style**: One of the 8 styles above
- **Aspect ratio**: 16:9 (standard) or 4:3 (classic)
- **Content outline**: Key points for each slide

### Step 2: Create Presentation Plan

Structure the presentation as a plan with style guidelines:

```json
{
  "title": "Presentation Title",
  "style": "keynote",
  "style_guidelines": {
    "color_palette": "Deep black backgrounds, white text, single accent color",
    "typography": "Bold sans-serif headlines, clean body text, dramatic size contrast",
    "imagery": "High-quality photography, full-bleed images, cinematic composition",
    "layout": "Generous whitespace, centered focus, minimal elements per slide"
  },
  "aspect_ratio": "16:9",
  "slides": [
    {
      "slide_number": 1,
      "type": "title",
      "title": "Main Title",
      "subtitle": "Subtitle or tagline",
      "visual_description": "Detailed description for image generation"
    },
    {
      "slide_number": 2,
      "type": "content",
      "title": "Slide Title",
      "key_points": ["Point 1", "Point 2", "Point 3"],
      "visual_description": "Detailed description for image generation"
    }
  ]
}
```

### Step 3: Generate Slide Images Sequentially

**CRITICAL: Generate slides one by one, in order.** Each slide uses the previous slide as a style reference to maintain visual consistency. Never generate slides in parallel.

**First slide** — establishes the visual language:
- Include full style guidelines (colors, typography, effects) in the prompt
- Be extremely specific: hex color codes, font weights, blur values
- This slide sets the tone for the entire presentation

**Subsequent slides** — reference the previous slide:
- Start prompt with: "Continuing EXACT visual style from the reference image"
- Specify: "SAME gradient background, SAME glass/typography treatment"
- Always pass the previous slide image as a reference
- Include a consistency note emphasizing style matching

### Step 4: Compose into PPTX

Assemble the generated slide images into a PowerPoint file. Each image becomes a full-bleed slide background at the specified aspect ratio.

## Prompt Engineering for Quality

### Be Specific
```
BAD:  "professional slide about AI"
GOOD: "Presentation slide with glassmorphism design. Background: smooth
       gradient from deep purple (#667eea) through magenta to cyan (#00d4ff).
       Center: frosted glass panel with backdrop blur, rounded corners 32px,
       bold white title 'Introducing Nova AI' (72pt, font-weight 700).
       Floating 3D glass spheres creating depth. visionOS aesthetic."
```

### Include Exact Details
- Hex color codes (`#667eea` not "purple")
- Font weights (`700` not "bold")
- Effect values (`backdrop blur 20px`, `shadow 8px blur 30% opacity`)
- Design references (`visionOS aesthetic`, `Stripe website style`)

### Enforce Consistency
- In every slide after the first, use: "SAME", "EXACT", "MATCH" keywords
- Describe what must stay consistent: colors, glass treatment, shadow style, typography
- If a slide looks inconsistent, regenerate with stronger reference emphasis

## Style-Specific Color Palettes

| Style | Primary | Background | Text | Accent |
|---|---|---|---|---|
| glassmorphism | #667eea → #00d4ff gradient | Vibrant gradient | White #ffffff | Frosted white rgba(255,255,255,0.15) |
| dark-premium | #0a0a0a | Near-black | White #ffffff | Electric blue #00d4ff or gold #ffd700 |
| gradient-modern | #7c3aed → #ec4899 → #f97316 | Mesh gradient | White or dark | Contrasting accent |
| neo-brutalist | #000000, #ffffff | Stark white or black | Black or white | Hot pink #ff0080 or yellow #ffff00 |
| 3d-isometric | #8b5cf6, #14b8a6 | Light gray #fafafa | Dark charcoal | Warm coral #fb7185 |
| editorial | #2d2d2d, #f5f5f0 | Off-white | Charcoal | Burgundy #7c2d12 or navy #1e3a5f |
| minimal-swiss | #000000 | Pure white | True black | Swiss red #ff0000 |
| keynote | #000000 to #1d1d1f | Deep black | White | Apple blue #0071e3 |

## Design Principles

- **Negative space**: 40-60% empty space creates a premium feel
- **One focal point per slide**: one message, not a wall of text
- **Depth through layering**: shadows, transparency, z-depth
- **Typography hierarchy**: massive headlines (72pt+), comfortable body (18-24pt)
- **Color restraint**: one palette, 1-2 accent colors max

## Common Mistakes

- Generic prompts like "professional slide" — be specific with every detail
- Too many elements per slide — cluttered = unprofessional
- Inconsistent colors between slides — always reference the previous slide
- Skipping the reference image — this breaks visual consistency
- Mixing styles within one presentation
- Generating slides in parallel — must be sequential for consistency

## Recommended Styles by Context

| Context | Recommended Style |
|---|---|
| Tech product launch | glassmorphism, gradient-modern |
| Luxury/premium brand | dark-premium, editorial |
| Startup pitch | gradient-modern, minimal-swiss |
| Executive presentation | dark-premium, keynote |
| Creative agency | neo-brutalist, gradient-modern |
| Data/analytics | minimal-swiss, 3d-isometric |

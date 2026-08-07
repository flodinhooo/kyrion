# Kyrion Brand Guide

This document defines the current visual identity of the Kyrion platform and serves as the source of truth for logos, icons, colors, and future product branding.

The goal is consistency across the entire Kyrion ecosystem.

---

# 1. Brand Architecture

Kyrion is the platform brand.

Individual products and modules may later receive their own names and visual identities, but they should remain clearly recognizable as part of the same Kyrion family.

Current and planned examples:

- Kyrion
- K-Core
- Velora
- K-Link
- K-OS
- K-Home
- K-AI

These products may use different accent colors or secondary symbols in the future, but should inherit the same fundamental design language.

---

# 2. Core Brand Symbol

The primary Kyrion symbol is the **K-Core mark**.

It consists of four geometric modules surrounding a colored central core.

The geometry is intentionally asymmetric and forms a recognizable **K**.

The symbol should communicate:

- connection
- modularity
- intelligence
- infrastructure
- automation
- technological precision

The central colored element represents the **Kyrion Core**.

It should remain one of the most consistent visual elements across the platform.

---

# 3. Core Meaning

The four surrounding modules can be interpreted as components of the Kyrion ecosystem connecting to a central intelligence layer.

Conceptually:

```text
        Module
           \
            \
Module ---- CORE ---- Module
            \
             \
            Module
```

The interpretation is intentionally abstract.

The logo should not be treated as an illustration of a specific architecture.

It is a brand symbol first.

---

# 4. Primary Brand Colors

## Dark Ink

Used for the light-theme K-Core mark and wordmark.

```text
#101E2D
```

Suggested usage:

- Light-theme logo
- Wordmark
- High-contrast typography
- Brand graphics

## Light Ink

Used for dark-theme marks and wordmarks.

```text
#F7F8FA
```

Suggested usage:

- Dark-theme logo
- Dark-theme wordmark
- High-contrast UI surfaces

---

# 5. Kyrion Core Gradient

The colored center is the primary accent element of the brand.

## Outer Ring

```text
Purple
#8B4DFF

Violet
#6C43F5

Blue
#168BFF
```

Recommended gradient direction:

```text
top-left → bottom-right
```

Approximate SVG definition:

```svg
<linearGradient
  x1="0%"
  y1="0%"
  x2="100%"
  y2="100%"
>
  <stop offset="0%" stop-color="#8B4DFF" />
  <stop offset="45%" stop-color="#6C43F5" />
  <stop offset="100%" stop-color="#168BFF" />
</linearGradient>
```

---

# 6. Core Interior

The center should appear luminous rather than flat.

Recommended colors:

```text
#FFFFFF
#E5FAFF
#8CDEFF
#53BFFF
```

Recommended radial gradient:

```svg
<radialGradient
  cx="40%"
  cy="35%"
  r="70%"
>
  <stop offset="0%" stop-color="#FFFFFF" />
  <stop offset="38%" stop-color="#E5FAFF" />
  <stop offset="72%" stop-color="#8CDEFF" />
  <stop offset="100%" stop-color="#53BFFF" />
</radialGradient>
```

The highlight should remain subtle.

Avoid making the core look metallic, glassy, or overly three-dimensional.

---

# 7. Core Glow

The core may use a restrained violet-blue glow.

Recommended base color:

```text
#684BFF
```

The glow should:

- remain centered around the core
- never overpower the K geometry
- become slightly stronger on dark backgrounds
- remain subtle on light backgrounds

Avoid excessive neon or cyberpunk styling.

Kyrion should feel modern and premium rather than visually aggressive.

---

# 8. Light Theme

Light-theme assets use:

```text
Primary mark:
#101E2D

Core:
Purple → Blue gradient
```

Preferred background:

```text
#FFFFFF
```

or similarly light neutral surfaces.

Files:

```text
branding/logo/k-light.svg
branding/logo/kyrion-light.svg
branding/icons/app-light.svg
```

---

# 9. Dark Theme

Dark-theme assets use:

```text
Primary mark:
#F7F8FA

Core:
Purple → Blue gradient
```

Preferred dark background range:

```text
#0B1421
#0E1626
#162437
```

Files:

```text
branding/logo/k-dark.svg
branding/logo/kyrion-dark.svg
branding/icons/app-dark.svg
```

The central core must remain visually consistent between themes.

---

# 10. Wordmark

The KYRION wordmark is custom-built using SVG paths.

It does not depend on an installed font.

This is intentional.

Characteristics:

- uppercase
- geometric
- wide tracking
- angular construction
- technical but restrained

Important letter characteristics:

## K

The vertical stem and diagonal arms are intentionally separated.

They must not touch.

The inner diagonal ends should appear sharp and geometric.

## Y

The Y uses a narrow central stem and wide upper arms.

## R

The R uses an angular shoulder and a sharp diagonal leg.

It should not resemble a conventional rounded typeface.

## I

Simple vertical geometric construction.

## O

The O is octagonal rather than circular.

This is one of the most important characteristics of the wordmark.

## N

The N uses a strong diagonal connection and geometric proportions.

---

# 11. Wordmark Spacing

Letter spacing is intentionally generous.

Do not compress the wordmark.

The spacing contributes strongly to the visual identity.

Preferred appearance:

```text
K  Y  R  I  O  N
```

rather than:

```text
KYRION
```

Do not manually alter spacing unless creating a separately approved lockup.

---

# 12. Divider

Full Kyrion lockups may use a thin vertical divider between the K-Core symbol and the wordmark.

Light theme:

```text
Color:
#101E2D

Opacity:
~28%
```

Dark theme:

```text
Color:
#F7F8FA

Opacity:
~32%
```

The divider should remain secondary.

It must never visually compete with the logo.

---

# 13. Logo Variants

## K-Core only

Use when space is limited or when the Kyrion identity is already known.

Files:

```text
branding/logo/k-light.svg
branding/logo/k-dark.svg
```

Typical uses:

- application navigation
- compact headers
- avatars
- loading screens
- product surfaces
- splash screens

## Full Kyrion Lockup

Contains:

```text
K-Core + divider + KYRION
```

Files:

```text
branding/logo/kyrion-light.svg
branding/logo/kyrion-dark.svg
```

Typical uses:

- landing pages
- documentation
- GitHub
- presentations
- marketing
- login screens
- product introductions

---

# 14. Favicon

Current file:

```text
branding/favicon/favicon.svg
```

The favicon uses the K-Core symbol without a fixed background.

The SVG background should remain transparent.

This allows browsers and operating systems to render it appropriately in different themes.

The favicon may use slightly stronger proportions or core emphasis than the full-size logo to improve readability at very small sizes.

---

# 15. Application Icons

Files:

```text
branding/icons/app-light.svg
branding/icons/app-dark.svg
```

Application icons use a contained rounded tile.

## Light

Recommended background:

```text
#FFFFFF
→
#F5F7FB
```

K-Core:

```text
#101E2D
```

## Dark

Recommended background:

```text
#162437
→
#0B1421
```

K-Core:

```text
#F7F8FA
```

The central purple-blue core remains identical.

---

# 16. App Icon Shape

Current master proportions:

```text
Canvas:
1024 × 1024

Tile:
960 × 960

Outer inset:
32 px

Corner radius:
196 px
```

The icon should retain generous internal spacing.

Do not scale the K-Core until it nearly touches the tile edges.

---

# 17. Background Philosophy

Kyrion branding should primarily use neutral surfaces.

Preferred:

```text
white
off-white
deep navy
near-black
```

Avoid:

- saturated full-background gradients
- neon-heavy backgrounds
- bright red
- aggressive RGB effects
- excessive glassmorphism
- noisy textures

The core provides the brand color.

The rest of the identity should remain restrained.

---

# 18. Clear Space

Always maintain sufficient clear space around the logo.

As a general rule, use at least the diameter of the central core as the minimum clear space around the outer K geometry.

For full wordmarks, maintain additional horizontal breathing room.

Do not place:

- text
- borders
- UI controls
- illustrations
- other logos

directly against the mark.

---

# 19. Minimum Size

The full wordmark should not be used when the text becomes difficult to read.

Recommended usage:

```text
Large:
Full Kyrion lockup

Medium:
K-Core or full lockup depending on context

Small:
K-Core only

Very small:
favicon.svg
```

At very small sizes, visual recognition is more important than retaining every fine geometric detail.

---

# 20. Logo Misuse

Do not:

- rotate the K-Core
- stretch the logo
- alter the K proportions
- move the core
- recolor individual K modules
- replace the core gradient randomly
- add outlines around the full mark
- use drop shadows on the K geometry itself
- change wordmark letter spacing casually
- substitute the wordmark with a normal font
- place the dark logo on dark surfaces
- place the light logo on light surfaces

---

# 21. Product Family

Future Kyrion products should share recognizable DNA.

Possible family:

```text
Kyrion
K-Core
Velora
K-Link
K-OS
K-Home
K-AI
```

The current recommendation is to preserve:

- geometric construction
- neutral surfaces
- central-core concept
- strong light/dark variants
- restrained gradients
- consistent icon framing

Products may receive their own:

- accent color
- secondary symbol
- animation
- icon detail
- supporting graphic language

They should still clearly belong to Kyrion.

---

# 22. Product Color Strategy

The main Kyrion brand owns the purple-blue core.

Future products may derive their own accent from this system.

Possible direction:

```text
Kyrion / K-Core
Purple → Blue

Velora
Violet → Cyan

K-Link
Blue → Cyan

K-Home
Blue → Emerald

K-AI
Violet → Electric Blue

K-OS
Neutral → Blue
```

These values are conceptual and not yet official.

Do not implement them as final product colors until the individual product identities are designed.

---

# 23. Motion

The central core is the preferred element for future motion design.

Possible states:

## Idle

Very subtle glow.

## Listening

Slow pulse.

## Speaking

Responsive radial movement.

## Thinking

Soft rotating or breathing gradient.

## Processing

Controlled rhythmic pulse.

## Connection established

Short outward glow.

The K geometry itself should normally remain static.

Motion should originate from the core.

---

# 24. Velora Integration

Velora should not require a completely unrelated visual identity.

Its design should inherit the Kyrion system.

Possible future concept:

```text
Kyrion K-Core
        ↓
animated central core
        ↓
Velora voice state
```

This makes Velora feel like an intelligence living inside the Kyrion ecosystem rather than a separate application.

---

# 25. Source Files

Current brand structure:

```text
branding/
├── favicon/
│   └── favicon.svg
│
├── icons/
│   ├── app-light.svg
│   └── app-dark.svg
│
├── logo/
│   ├── k-light.svg
│   ├── k-dark.svg
│   ├── kyrion-light.svg
│   └── kyrion-dark.svg
│
├── master/
│   └── k-master.svg
│
├── social/
│
└── brand-guide.md
```

---

# 26. File Responsibilities

## `master/k-master.svg`

Geometry source for the K-Core symbol.

Should not contain application-specific backgrounds.

## `logo/k-light.svg`

Standalone K-Core for light surfaces.

## `logo/k-dark.svg`

Standalone K-Core for dark surfaces.

## `logo/kyrion-light.svg`

Full Kyrion lockup for light surfaces.

## `logo/kyrion-dark.svg`

Full Kyrion lockup for dark surfaces.

## `favicon/favicon.svg`

Small-size optimized K-Core.

Transparent background.

## `icons/app-light.svg`

Light application icon.

## `icons/app-dark.svg`

Dark application icon.

---

# 27. Export Strategy

SVG should remain the primary source format.

From the SVG masters, generate raster exports when required.

Recommended PNG sizes:

```text
16 × 16
32 × 32
48 × 48
64 × 64
128 × 128
256 × 256
512 × 512
1024 × 1024
```

Do not manually redraw PNG variants.

Always export them from the SVG source.

---

# 28. Design Principles

The Kyrion visual identity should feel:

- intelligent
- precise
- premium
- modular
- calm
- trustworthy
- technological
- modern
- recognizable

It should not feel:

- childish
- gaming-focused
- cyberpunk
- aggressive
- excessively futuristic
- visually noisy
- generic AI-generated branding

---

# 29. Guiding Principle

The core idea of the Kyrion identity is:

> **Complex systems connected through one intelligent core.**

The visual system should reinforce that idea without needing to explain it explicitly.

The logo should remain strong even when the viewer knows nothing about Kyrion.

---

# 30. Status

Current status:

```text
K-Core geometry         approved
Light K logo            approved
Dark K logo             approved
Light Kyrion wordmark   approved
Dark Kyrion wordmark    approved
Favicon                  created
Light app icon           created
Dark app icon            created
Social assets            pending
Product identities       pending
```

This document should evolve together with the Kyrion platform.

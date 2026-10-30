# Product credibility and visual evolution

## Audit

Reviewed the root README and agent rules, product strategy, roadmap, installer
implementation status, RBAC documentation, the previous website review, recent
commits, current website source/tests, Core and Web feature locations, and the
live German homepage on 2026-10-19. Live content still precedes the previous
repository refresh; this work does not deploy it.

The existing bilingual routes, recognizable logos, explicit prototype status,
local system fonts, semantic components and reproducible asset/build pipeline
already provide a strong foundation. Credibility suffered from repeated
architecture sections, experimental voice leading the product story, verbose
headings, oversized section spacing and inactive documentation controls.

- Developers need concrete implementation boundaries and readable architecture.
  Preserve Core authority, integration limits and direct repository links.
- Everyday users need a quick purpose, practical examples and a clear next step.
  Lead with home control, Calendar/media and accounts instead of experimental AI.
- Partners need coherent identity and honest delivery scope. State independent
  development and prototype readiness without invented commercial evidence.

The only documentation image inspected is a startup-command capture, unsuitable
as a product preview. No screenshot or application interface was fabricated.
The hero summary is plain editorial content labeled as implemented prototype
capabilities, with a direct link to the full limitations.

## Design and messaging

Dark is the initial theme. Existing light and system preferences are retained.
Website-only charcoal surfaces replace the blue-heavy dark surfaces; violet
provides the primary action hierarchy and amber highlights status sparingly.
The existing logo, Core gradient, system-font direction, routes and components
remain. No dependencies, shared brand assets or hosting settings are changed.

The hero says "Your home. One system. Your control." in English, with matching
German copy. It explains the Local-First Home Operating System and offers
working Product and GitHub links. A factual capability summary replaces the
large decorative orbit. Implemented benefits appear before Velora. The repeated
ecosystem section is removed; the architecture flow remains. Spacing and shared
heading sizes are tightened. Footer copy identifies independent development.
The final CTA links to GitHub and documentation.

The diagram now describes Web as an available interface and voice as
experimental. Its connectors had retained an obsolete invisible reveal style;
they are now visible, including without JavaScript. Product icons follow their
capability when status filtering changes. Documentation navigation consists of
real technical-guide links rather than disabled search/version placeholders.

## Capability boundaries

Retains the evidence and limitations in [REFRESH.md](REFRESH.md): Core-owned
identity, policy and action history; installation-wide roles; selected lighting
paths; local Calendar and read-only Google display; Spotify Connect and YouTube
link playback. Voice reliability, HA physical acceptance and installer release
acceptance remain open. General automations, resource-scoped permissions,
mobile and wider plugin capabilities remain planned. The root README/roadmap
installer conflict is documented rather than silently resolved.

## Verification

Final local results: production build, TypeScript and ESLint pass; **27
Playwright tests pass**. Prettier is checked after final formatting. Playwright
covers bilingual routes, metadata, theme persistence, mobile navigation,
no-JavaScript rendering, reduced motion, voice interaction, contact boundaries,
internal links and responsive overflow. Added dark-default persistence,
hero destinations, 390/768/1440px screenshots and a minimum 4.5:1 check for key
dark-theme text tokens and primary-button labels. The violet button was
adjusted from #8B5CF6 to #8250E8 to provide approximately 4.93:1 white-label
contrast. This is targeted contrast coverage, not a complete accessibility audit.

The first run found two test issues: documentation links now appear in both
navigation and article cards, and minified CSS can shorten hex colors. Selectors
and color parsing were corrected. Browser screenshots were visually inspected
at desktop, tablet and mobile widths in addition to light-theme screenshots.
Chromium is the available browser target; Safari/Firefox and physical touch
hardware were not tested. No live SMTP delivery, production deployment or
hardware acceptance is performed by these tests.

## Further recommendations

1. Capture a reviewed, anonymized screenshot of the actual Web application.
2. Add the public website checks to CI independently of `apps/web`.
3. Reconcile root installer documentation with its implementation-status file.
4. Confirm one canonical apex/www domain at hosting level.
5. Review the license and publish contribution guidance before inviting reuse.

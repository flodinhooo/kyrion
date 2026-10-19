# Kyrion public website

Standalone public Next.js App Router website for kyrion.ch. It presents the
Kyrion development prototype without authentication, device APIs, databases,
private installation data or a dependency on `apps/web`.

## Pages and content

- `/`: platform introduction and ecosystem overview;
- `/product`: implemented prototype capabilities versus experimental/planned work;
- `/about`: purpose, ownership and local-first principles;
- `/development`: status definitions, current focus and outcome-oriented direction;
- `/docs`: documentation layout preview, with repository documentation links.
- `/contact`: public inquiries and optional interest in future testing.

German is the default language, with no URL prefix. Every page has an English
equivalent under `/en`. Old `/de` URLs permanently redirect to the unprefixed
German page. English remains the locale-resource type/fallback reference. A statically generated, allowlisted catch-all route shares the page
implementations and resolves the correct HTML language and metadata on the
server. Unknown paths return 404. Content lives in `src/locales/{en,de}.json`.
The header language link retains the current page.

Capability statements are synchronized with repository code, the root README,
`docs/rbac.md`, the security hardening closeout, integration documents and
`docs/installer-v1-implementation-status.md`. See [refresh review](REFRESH.md)
for evidence and known documentation conflicts. "Available" means implemented
in the prototype, not a general release. Installation-wide roles and Calendar
are implemented; resource scopes, general automations, mobile and public plugins
remain planned. Voice reliability and physical HA acceptance remain open.
Update both locales when development claims change.

## Development

Run from the repository root with Node.js 20.9 or newer and pnpm 10.29.3:

```sh
pnpm install --frozen-lockfile
pnpm --filter website dev
```

Open http://localhost:3001. Port 3001 keeps the website separate from the local
Kyrion Web application's default port 3000.

Validation and production startup:

```sh
pnpm --filter website lint
pnpm --filter website format:check
pnpm --filter website typecheck
pnpm --filter website build
pnpm --filter website exec playwright install chromium
pnpm --filter website test
pnpm --filter website start
```

Next.js generates `next-env.d.ts` during development, type generation and builds.
Dependencies, `.next` output and TypeScript build metadata are ignored by Git.
`pnpm --filter website format` applies Prettier. Playwright starts the production
server itself on port 3101, leaving development port 3001 alone. Tests cover localized pages,
metadata, 404s, system/explicit themes, persistence, keyboard/mobile navigation,
small-screen overflow, reduced motion and generated assets.

## Styling and branding

Tailwind CSS v4 handles layout and component styles. `globals.css` contains
only semantic theme tokens, typography, global accessibility rules and brand
effects. `components/ui/button.tsx` uses the shadcn/ui Button pattern with Radix
Slot, CVA and the local `cn` helper. `components.json` supports future additions.
The site uses a local system font stack; it makes no runtime font requests.

The public site retains Kyrion's logos and Core gradient, with a dark-first
charcoal/violet presentation and restrained amber status details. The palette
is local to the website; root branding and the local application's styling
remain unchanged. System fonts avoid runtime font requests.

`scripts/prepare-branding.mjs` runs before `dev` and `build`:

- copies the four approved logo SVGs and favicon from root `branding/`;
- exports a 180px touch icon from `branding/icons/app-light.svg`;
- exports a 1200x630 PNG using the dark wordmark on brand navy for social cards.

All outputs are ignored under `public/branding/`. No second tracked asset source
is created. The monorepo checkout, including `branding/`, must be available at
build time; deploy the generated public assets with the build. Sharp is a build
dependency for reproducible PNG exports. SVG logos retain their proportions and
use explicit image dimensions without unnecessary raster optimization.

The social SVG files currently contain zero bytes despite the brand guide
listing social assets as pending. The generated wordmark card is a baseline
until a reviewed social master exists; it does not claim to reuse a finished
social design. Root brand files and `apps/web` remain unchanged.

`next-themes` applies the saved theme before hydration using `data-theme`.
New visitors start in dark mode. Saved light, dark or system preferences remain
respected through `kyrion-website-theme`; the sun/moon button persists explicit
choices. Without JavaScript the CSS defaults to dark, including theme-specific
brand assets and status colors. Reduced-motion preferences disable animations
and transitions. If a CSP is added, allow the theme initialization script
through an appropriate nonce/hash to retain flash prevention.
The language link retains the current page.

The [product credibility review](PREMIUM.md) records the visual rationale,
audience audit, implemented capability evidence and verification limits.

## Publication boundaries

Canonical URLs, Open Graph metadata, robots and sitemap target `https://kyrion.ch`.
The informational site is indexable; a preview host should set its own noindex
policy before deployment. GitHub links use the repository's configured remote,
`https://github.com/flodinhooo/kyrion`; confirm public access before launch.

The website is deployed on Vercel at kyrion.ch. The contact form adds a bounded
server-side SMTP channel, separate from Kyrion Core. Configure the seven contact
variables and complete the live checks in [contact operations](CONTACT.md).
The Velora voice preview on the home page uses the optional static assets
`public/audio/velora-intro-de.mp3` and `public/audio/velora-intro-en.mp3`.
`VeloraVoicePreview` selects the asset from the active page locale, starts only
after an explicit click or keyboard activation, and fails softly when an asset
is missing. The repository includes both DE/EN voice samples. Playback requires explicit
click or keyboard activation; hover and focus alone do not start audio.
Vercel Analytics is included by the existing root layout. It remains separate
from the local platform; this website does not claim to be analytics-free.
No real delivery is attempted by tests. Full public docs, search, version
selection and signup handling are intentionally not implemented. No alpha access or release dates are
announced. The root licence decision remains pending; this site makes no
software reuse or commercial-availability promise.

The root pnpm workspace currently includes only `apps/website`. The pre-existing
`apps/web` workspace and lockfile remain independent and unchanged; continue
running its pnpm commands from that directory.

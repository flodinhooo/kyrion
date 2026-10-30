# Public website refresh review

## Scope and initial findings

The public site lives in `apps/website`, independently of `apps/web`: Next.js
16 App Router, React 19, strict TypeScript, Tailwind 4, shared UI components,
German/English JSON resources and system fonts. Public pages are prerendered;
contact delivery uses a server route. Existing Vercel Analytics is retained.
Brand assets are generated from root `branding/` during the existing build.
No dependencies, provider behavior, Core services, installer behavior or hosting
settings are changed. Branch: `refresh/public-website`. No production deployment.

The live German homepage was retrieved on 2026-10-19 with a direct HTTPS request.
`kyrion.ch` redirects to `www.kyrion.ch`; its content matched the stale claims in
the checkout. Recent website commits cover voice preview behavior, Analytics
and legal pages. The root CI currently checks `apps/web`, Core and installer;
it does not run the independent website checks.

## Content evidence and corrections

| Area           | Repository evidence                                                               | Website treatment                                                                   |
|----------------|-----------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| Positioning    | Root README; `docs/vision.md`; `docs/product-strategy.md`                         | Local-First Home Operating System; working prototype explicitly stated              |
| Roles          | `docs/rbac.md`; Core `security/Rbac.kt`; Web roles/user routes; security closeout | Installation-wide roles implemented; resource scopes planned                        |
| Calendar       | Core `calendar/LocalCalendar.kt`; Google integration; security closeout           | Local CRUD and read-only Google display implemented                                 |
| Media          | Spotify and YouTube integration documents; Core adapters; Web Lounge features     | Spotify Connect and YouTube link player implemented; receiver acceptance caveat     |
| Devices        | Root README; integration documents; gateway evidence                              | Hue through Zigbee; bounded OA20 Bluetooth, not generic support                     |
| Home Assistant | `docs/home-assistant-import.md`; Core adapter and Web setup                       | Read-only import; physical verification pending                                     |
| Velora         | Voice Satellite, Core voice sessions, AI provider code; dated voice evidence      | Developing assistant with working slices; reliability acceptance pending            |
| Installation   | Installer scripts, release workflow and implementation-status document            | Implemented fresh-install boundary; no released artifact bundle or consumer install |
| Future work    | Roadmap; mobile scaffold; marketplace document                                    | General automations, mobile, Matter/Thread and public plugins planned               |

The old Google permissions illustration simulated an account, management
controls and scopes that did not describe actual functionality. It is replaced
by a labeled architecture summary. YouTube uses a visible browser link player,
not Google account authorization. Documentation cards now link to actual setup,
installer status and architecture documents.

The root README and roadmap still call Installer v1 unimplemented, conflicting
with its implementation-status document and code. This refresh follows the
verified boundary and explicitly retains release gates. Those broad documents
should be reconciled by the installer workstream. Unrelated existing edits in
`docs/status/TODO.md` and `infrastructure/installer-v1` are preserved.

## Visual and technical changes

Retained navy/white surfaces, violet Core gradient, logos, typography direction,
page order, themes and routing. Adjusted card spacing, active navigation,
integration wrapping and tablet columns. Status badges resist compression.
Core architecture is now a server component, visible without JavaScript,
without IntersectionObserver or reveal transitions. Voice preview no longer
plays on hover/focus; its actual recordings remain click/keyboard controlled.
Metadata and social descriptions use the same accurate positioning.

## Verification

Verified locally on 2026-10-19: `pnpm --filter website lint`, `format:check`,
`typecheck`, `build` and `test` pass. Playwright: **26 passed** in Chromium.
Screenshots were reviewed for the desktop homepage and mobile navigation;
responsive overflow checks cover 320px, 390px, 768px and desktop layouts.
GitHub and the linked documentation returned HTTP 200.

The first browser run found that the decorative Velora halo intercepted pointer
events; the corrected halo ignores pointer events, and click/pause coverage
passes. A concurrent lint run encountered disappearing Playwright artifacts;
generated test/report directories are now ignored and lint passes. Initial
formatting failures were corrected. No unresolved test failures remain.

The Playwright suite
covers both locales, public routes, metadata, theme persistence, keyboard/mobile
navigation, assets, voice activation, no-JavaScript architecture, prototype
claims, real documentation links and tablet overflow/internal navigation.

## Remaining recommendations

Reconcile root installer documentation, add independent website checks to CI,
and choose the repository license before making reuse claims. Confirm the
preferred apex/www domain at hosting level before changing canonical policy.
Keep hardware acceptance and release readiness distinct from code presence.

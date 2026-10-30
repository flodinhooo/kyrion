# Public website product review — 2026-10-30

This review covers the shared `refresh/product-credibility` checkout at
`082b661`, not a deployment. Initial Git status contained only dirty nested
calendar-recovery and Spaces worktrees. They were inspected read-only and left
untouched. No implementation was imported from either feature branch.

## Sources and presentation

- Root `README.md`, `docs/{vision,principles,product-strategy,architecture}.md`:
  local-first modular platform, optional providers, Core authority, prototype
  status and separate evidence categories.
- `docs/agent-handoffs/stabilization-handover.md`, its Sprint 02–04 references,
  and `docs/calendar-synchronization.md`: bounded Calendar editing and explicit
  per-event synchronization, marked live Google checks, operational and Voice
  limits. Earlier website and README statements that Google is entirely
  read-only are stale. All-day and recurring Google instances remain read-only.
- `docs/agent-handoffs/kai-velora-handover.md`, `docs/ai-model-providers.md`,
  `docs/personal-context-engine.md`, and shared `ModelRouter`, `ContextBuilder`
  and `AiOrchestration` code: implemented model selection, optional personal
  context, real local generation versus simulated cloud transport. Cloud
  receives the consented current message only, not personal context sources.
  Satellite identity does not identify a speaker or authorize private context.
- `docs/agent-handoffs/kdata-handover.md`, `docs/k-data.md`, and shared
  `knowledge/` Core and Web code: initial personal PDF/text ingestion/retrieval
  exists. Tested completion/security fixes at `25b6fee` in `feat/k-data-m01`
  are not evidence of integration or deployment. Real-model RAG, browser,
  runtime and database-plus-file restore acceptance remain open. Team knowledge,
  OCR and cloud document context are not available.
- Read-only Spaces branch evidence: `.worktrees/kyrion-spaces/docs/status/
kyrion-spaces-agent-3.md`, `docs/kyrion-spaces.md` and
  `docs/spaces-tenant-audit.md` in that worktree. The initial handoff describes
  missing verified BUSINESS domain restrictions; later in-progress documents
  describe additional identity/domain work and bounded isolation tests.
  These are evolving branch snapshots, not an integrated final acceptance.
  No Spaces handover exists in the shared `docs/agent-handoffs/` at review time.
  HOME/BUSINESS, memberships and invitations are presented as separate work;
  domain verification and complete isolation are explicitly unvalidated.
- `docs/home-assistant-import.md`, `docs/installer-v1-implementation-status.md`,
  `docs/development-startup.md` and existing hardware evidence: bounded device
  support, read-only HA import, separately configured local services and no
  released consumer installer. Physical evidence is specific to tested models.
- Existing locale legal/contact resources confirm `hello@kyrion.ch`; audience
  CTAs use the existing localized `/contact` route and its real SMTP handler.
  No registration, ordering, new form or delivery simulation was added.

## Result

Home retains the established visual design and adds visible audience entries
and a current AI/knowledge/Spaces overview. `/private` and `/business`, plus
their `/en` equivalents, share presentation components and separate translated
content. Navigation, active state, language retention, metadata, redirects and
sitemap use the existing allowlisted route convention. About and Docs remain
available in the footer. Status wording now says “Implemented in prototype”
rather than unqualified “Available”. Business examples are explicitly planned.

## Reconcile after the fourth handover

Recheck the final Spaces commit and shared integration before changing claims
about HOME/BUSINESS setup, verified domain policies, memberships/invitations,
role scope or isolation. Require combined evidence for personal documents,
retrieval, asynchronous workers, AI streams, integrations and restoration.
Reconcile the documented V37 collision and other migration histories through
their owners; this website change performs no migration or merge. Check K-Data
completion integration, local-model acceptance, release artifacts and operating
evidence separately. Branch test totals must never become release claims.

## Verification

- `pnpm --filter website lint`: passed.
- `pnpm --filter website typecheck`: passed.
- `pnpm --filter website build`: passed; both audience routes generated in DE/EN.
- `pnpm --filter website test`: 28 passed in Chromium. Includes metadata,
  sitemap, legacy redirects, language retention, contact boundaries, keyboard
  navigation, themes, reduced motion, and 320/390/768/1440px layout checks.
  The new audience flow covers DE/EN at 390px and 1440px. It sends no real mail.
- Screenshots inspected: desktop home, mobile private and desktop business;
  the test run also produced all audience/locale/viewport screenshots.
- Prettier on all changed files and `git diff --check`: passed.
- Full `format:check`: fails on unchanged pre-existing `REFRESH.md`,
  `src/components/pages/docs.tsx` and `src/components/site-ui.tsx`.
  They were left untouched to avoid unrelated formatting changes.

The first browser run exposed two outdated text assertions (the former home
description and an internal module name absent from the reader-facing page).
Those assertions were corrected; the final complete run passed. A local shell
encoding issue in newly entered translations was corrected before that run.
No public SMTP delivery, other browser engines, backend regression or new
hardware acceptance was performed. No publication or deployment occurred.

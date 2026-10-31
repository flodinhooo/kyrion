# Public website product review — 2026-10-30

The initial review covered the shared `refresh/product-credibility` checkout at
`082b661`, not a deployment. The final four-handover review used shared HEAD
`ac7e87d` and Spaces documentation commit `024e1e6`. Initial Git status contained only dirty nested
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
- Final Spaces handover, read-only: `.worktrees/kyrion-spaces/docs/agent-handoffs/spaces-handover.md`
  at `024e1e6`, with `docs/kyrion-spaces.md` and `docs/spaces-tenant-audit.md`
  in that worktree. All four final handovers are now available; the Spaces one
  remains branch-local. Milestone 02 supersedes the initial report's missing
  domain enforcement/recovery statements. Spaces, memberships, invitations,
  email/DNS domain proof and protected local owner recovery are implemented and
  tested separately. `BusinessIdentityService` and `TenantBoundary.voice` in
  that branch confirm the implementation and Business voice guard. Actual
  mailbox/DNS deployment, interactive recovery and combined integration remain
  unvalidated. Multi-Space runtime stays blocked; targeted two-Space tests do
  not establish complete isolation. Knowledge APIs are absent in that branch,
  so its tests cannot establish document/RAG isolation. No branch implementation
  was imported. Public copy now distinguishes implemented branch capabilities
  from shared availability and real operational acceptance.
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

## Follow-up after the final four-handover review

The fourth handover has been reviewed; it does not change the Business release
boundary. Recheck shared integration before changing claims about available
HOME/BUSINESS setup, verified domain policies, memberships/invitations, role
scope or isolation. Require combined evidence for personal documents,
retrieval, asynchronous workers, AI streams, integrations and restoration.
Reconcile the documented V37 collision and other migration histories through
their owners; this website change performs no migration or merge. Check K-Data
completion integration, local-model acceptance, release artifacts and operating
evidence separately. Branch test totals must never become release claims.

## Verification

Lint, typecheck, build and the complete 28-test browser suite passed again after
the final Spaces handover updates. The audience test now explicitly checks the
separate-branch integration boundary and disabled Business voice in both locales.
The updated mobile Business screenshot was inspected. The full formatting check
still reports only the three unchanged files listed below.

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

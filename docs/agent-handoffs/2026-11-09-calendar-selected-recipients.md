# Selected calendar recipients and settings usability

Source prepared on master, 2026-11-09. V47 is **not applied** to the personal
Windows database; the guarded live Core remains V46. Pi activation is outside
this change's proposed local rollout. No real provider writes or sharing changes
were made during verification.

## Behavior

The Google destination card now clearly separates receiving manual copies from
sharing one's own calendar. Its heading, explanation, opt-in, calendar selection
and actions are readable on desktop and mobile; extended consent stays available.

Personal disclosure gains per-calendar recipient checkboxes backed by Core
authorization and V47, as ADR 0044 describes. Unselected owners cannot enumerate
or read a source; in-flight reads revalidate grants. Existing disclosures migrate
to a fixed audience of current active household accounts. No future-member grant
or new role/provider authority is introduced. Older Cores advertise no recipient
capability: Web disables positive sharing changes but still permits revocation.

Main implementation: `PersonalCalendarDisclosure.kt`, additive V47,
`personal-disclosure.tsx`, `disclosure-{model,server}.ts`,
`household-destination.tsx`, locale resources and scoped calendar styles.
The schema-only tool accepts explicit target47 under its existing protections.
V1–V46 SQL is unchanged; successful read-only planning validates its history.

## Verification

- Core boot JAR built; 17 disclosure integration cases and the migration-history
  regression passed on disposable PostgreSQL.
- Actual schema-only tool V46→V47 plan/apply rehearsal passed: old account,
  credential and disclosure data unchanged; explicit recipient snapshot correct.
- Testcontainers had Ryuk/reuse disabled. Main disclosure and monitored rehearsal
  containers had zero mounts and were removed after successful JUnit completion.
- 273 Web tests, ESLint, TypeScript and Next production build passed.
- 14 schema-tool Python tests, Ruff lint and formatting checks passed.
- Isolated Chromium checks passed in DE/EN: selecting only one of two recipients,
  reload persistence, empty-selection prevention, old-runtime fallback/revocation,
  target selection and desktop/mobile layout. No real Core/provider credentials
  were used by the browser fixture.
- Local PostgreSQL/Web/Core/AI/Ollama/STT/TTS readiness remained green.

## Prepared local activation

Immutable tested Core candidate SHA-256:
`0a5fc276d3ca1cf8ddd33620ec85e839a8190c4f6ce34acc13755621840f38c9`.
Protected artifact and read-only plan are below
`.run/dev-recovery/selected-recipient-rollout/`. The plan binds the existing
Windows database identity, artifact, tool and table fingerprints, from46 to47.
An existing protected operator connection file was reused directly; no new
database-password file was created. The preliminary plan must be refreshed in
the approved maintenance window because normal activity can change fingerprints.

ADR 0040 requires separate target/recovery/maintenance approval. Before applying:
prepare and verify a current recovery set, stop only the reviewed local Core,
refresh/review the quiet-target plan, apply47, pin/start the reviewed artifact
through the existing guarded LAN launcher, and verify Core/Web/Pi connectivity
and recipient isolation. A database restore, not a blind old-JAR restart against
V47, is the rollback boundary. Do not touch Pi's database or deploy to the public
website as part of this local activation. Real partner/Google/phone acceptance
remains separate from the synthetic evidence.

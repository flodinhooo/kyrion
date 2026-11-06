# Personal calendar disclosure results (Assignment A follow-up)

Status: HOME-03 Google slice implemented and automatically verified; not deployed.
Baseline: master `fba7cbb`, following native events `69cee10` and Gateway `c398402`.
Decision: [ADR 0037](../adr/0037-voluntary-personal-calendar-disclosure.md).

## Result

Each connecting HOME account can explicitly save private, availability-only or
detail visibility for an actual personal Google calendar. The audience is current
active household members with calendar read access. OWNER cannot override consent.
Settings require calendar read/update permissions, an actual readable source and
an expected revision. No role grants or previous personal data are reclassified.

Core lists opaque shared sources and returns a bounded read-only projection.
Availability has event time boundaries and opaque IDs only. Details additionally
has title/description; neither projection contains provider IDs, ETags, email,
calendar names or credentials. Own settings remain personal. An expected connection
guard checks the actual token connection before provider access. Disconnect deletes
opt-ins; new connections do not inherit consent.

V44 adds only disclosure rows with composite account/Space and connection/account
foreign keys. Transactional audit records actor/Space/disclosure/correlation without
calendar content. Provider HTTP occurs outside transactions. Final authorization
and redaction serialize with role/disclosure changes; an in-flight changed revision
is rejected rather than returning previously authorized details. Private revocation
does not require contacting the provider. No shared representations are persisted.

The Web calendar adds DE/EN personal sharing settings and explicit consent, plus
one selected shared-source overlay and a read-only details dialog. Person filters
remain display-only. Shared data and the derived details dialog disappear on refresh
failure/revocation; requests are no-store. Visible views refresh every 30 seconds
and on focus; hidden views clear their shared data. Already seen/copied information
cannot be recalled. Existing local, native household, own Google and linked sync
paths remain separate. Shared events cannot enter an editing/deletion path.

## Verification

- Initial focused Core: 24 passed (10 disclosure, 10 household, 4 existing Google).
- Web: 218 tests passed, ESLint, TypeScript and the final isolated production build
  passed, including the read-only detail UI. Only Next's generated temporary build
  directory includes were removed from tsconfig; no configuration change is delivered.
- Final combined Core: **386 tests**, zero failures/errors/skips; `bootJar` passed.
  This includes disclosure13, household10, Google5, Gateway28 and rollout rehearsal1.
  B's exclusive runner records unchanged Core before/after source manifests and
  actual artifact inventory through V44. The separate Gateway dump/restore upgrade
  rehearsal targets V43; it does not certify a V44 production upgrade. Its discovered
  malformed historical-payload queue defect was reproduced, fixed by B and covered
  by the passing combined run. No A source was changed during final acceptance.
- Evidence is under ignored `.run/dev-recovery/gateway-acceptance/`, in the run
  started `2026-11-06T13:00:36Z` (`full-core`, passed). A's focused/Web logs are
  under `.run/dev-recovery/coordination/home-disclosure-*`. Starting HEAD was
  `fba7cbb` plus the frozen A/B changes; later commits attribute those changes.
- No new dependencies. No dedicated Core formatter/linter task is configured.

## Coordination and limits

Assignment B owns the Gateway migration rehearsal, runner, Gateway-only repairs
and rollout documentation. A owns V44, ADR0037, Calendar, Google read boundary,
Web and this report. Git/core FileShare.None locks and explicit staged paths remain
mandatory. The reusable second-chat prompt is [recorded separately](2026-11-06-gateway-follow-up-prompt.md).

No deployment, runtime restart, live migration, real provider call/write, account
reset or device action was performed by A. This is source verification, not live
browser/provider acceptance. Windows remains its existing runtime; Pi state must
be freshly checked before rollout. Permission restoration can restore a retained
opt-in; choose Private or disconnect to revoke it independently of role changes.

Remaining: additional providers, simultaneous source overlays, recurring/all-day
authoring, full offline replication, free-slot suggestions, HOME-04 destination
writes and live family acceptance. No AI/Voice context integration was added;
future consumers must use the same Core redaction boundary. Multi-HOME membership
and cross-installation identities remain separate milestones.

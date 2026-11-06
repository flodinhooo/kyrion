# HOME-05 first calendar usability results (Chat A)

Status: source and isolated browser-fixture checks passed; not a live rollout.
Baseline: master `e3d9ff4`; concurrent B delivered V45 migration tooling in
`209217a` and its report in `d78e212`. Both remain on master.
Decision: [ADR 0039](../adr/0039-owned-calendar-copy-presentation.md).
Parallel prompt: [V45 migration follow-up](2026-11-06-v45-upgrade-parallel-prompt.md).

## Result

An authenticated Core read endpoint exposes only the caller's confirmed owned
household-copy links for the actual selected Google calendar, with current HOME,
connection, recipient grant/permissions, membership, delivered/native revision and
bounded range checks. The Web server suppresses a Google copy only alongside a
successfully loaded identical native event, checking identity/marker, ETag,
revision, content and exact timed boundaries including sub-millisecond precision.
Changed, uncertain, revoked, independent, all-day/recurring or unverifiable copies
remain visible. Optional-link failure preserves calendar data and explains possible
duplicates. Correlation metadata is absent from the combined browser response.
Other members' availability-only projections are deliberately not expanded with
native/provider identity; their overlays remain independent display choices.

Existing datetime-local fields preserve their original absolute instants when
unchanged. Title-only edits no longer truncate seconds/precision or shift the
second repeated autumn hour to its first occurrence. Newly entered nonexistent
spring times and invalid calendar dates fail with localized feedback. Native,
legacy local and own Google editors share the correction. The HTML end-time minimum
was removed because comparing wall times rejects valid events across a repeated
hour; Core continues validating absolute start/end ordering. Explicit authoring of
either occurrence of a newly entered ambiguous time remains separate UI work.

Actual browser testing exposed an additional defect: the enlarged event form's
Save button was outside a fixed backdrop and could not be reached at 1440x1100.
Scoped Calendar CSS now limits dialog height to the viewport and scrolls its
content, including on mobile. Fresh editor openings clear prior stale-conflict
messages. No migration, role grant, provider mutation or new dependency is added.

## Verification

- Full Web **246 tests** passed, including exact-copy mismatch/fallback tests and
  isolated real Node timezone probes in Europe/Zurich, America/New_York and UTC.
  Existing TypeScript dev tooling compiles the actual editor module for the probes.
  ESLint, TypeScript and the final isolated production build passed. Next's two
  generated temporary build-directory includes are removed from tsconfig only.
- Combined Core **422 tests**, zero failures/errors/skips, bootJar passed. Includes
  A's delivery/copy-link suite30 and B's migration rehearsal6. B held the exclusive
  Core lock and recorded stable Core/tool hashes in
  `.run/dev-recovery/schema-acceptance/431da2a67e9842beb11a99951e21ae11/`.
  A's metadata source and six new backend regressions were frozen throughout;
  no subsequent Core edit was made. No repeat build is claimed or needed for an
  unchanged source tree. B's report records artifact scope and exact bytes.
- Chrome **156.0.8078.81**, real isolated production Web build, synthetic loopback
  Core only, two separate browser contexts/cookie stores, Europe/Zurich:
  confirmed copy merge; month/week/day controls; two-user joint edits; no provider
  write on native save; stale-revision conflict; unsaved-edit delivery block;
  explicit recipient confirmation and visible partial result; read-only busy
  overlay; revocation clearing overlay and open details; fresh reopen clearing
  old conflict; explicit-participant shared creation; German/English and light/dark.
- Final rebuilt production CSS, without injected styles, passed reachable Save at
  desktop and **390x844**. The mobile dialog bounds were x16/y16/358x812;
  scrollHeight1213 exceeded clientHeight810, its bottom828 stayed inside844, and
  document width390 matched the viewport. Actual click/scroll/save succeeded;
  no forced clicks or JavaScript form submission substituted for the interaction.
  No browser page errors were observed in the accepted flows.

Browser checks used existing ignored local Playwright tooling, not a new project
dependency, and synthetic fake accounts/events/tokens only. Helpers/evidence live
under `.run/dev-recovery/coordination/home05-*` and `home-usability-*`; the owned
test Web/Core and headless browser are stopped after verification. An early browser
tool timeout was replaced by a separately running synthetic backend. A subsequent
build met a Windows lock from the still-running owned fixture; only that fixture
was verified/stopped and the final build passed. These are test-environment
diagnostics, not claims of a production service failure or restart.

## Files and remaining boundary

Core: new `calendar/HouseholdCopyLinks.kt`, six focused regressions in the existing
owned delivery integration suite. Web: Calendar model/page/combined route,
`owned-copy-presentation.ts` and tests, DST tests, dirty-state helper, DE/EN messages
and scoped Calendar dialog rules in globals.css. Documentation: ADR0039, reusable
parallel prompt, this report and first-use readiness/plan/TODO updates. B's source,
tools, SQL, ADR0040 and reports are preserved and not staged by A.

No real account, calendar, device, operational database or private dump/key was
modified by the feature verification. The synthetic browser is not disposable live-provider
acceptance. See [first-use readiness](../home-first-use-readiness.md) for remaining
original-data/key restore, protected target checks, exact release/ARM64 provenance,
controlled activation and human calendar/hardware acceptance. Business, multi-HOME,
new providers and recurrence authoring remain deliberate later product scope.

## Separate authorized local service recovery

The final live readiness observation found AI8000, STT8040 and TTS8020 down;
PostgreSQL5432, Web3000, Core8080 and Ollama11434 were already ready. The original
owner instruction to start missing services remains applicable. The existing
operator helper failed closed during its ACL initialization (`COMMAND_FAILED`),
so no ACL was weakened, key replaced or helper security check disabled. After
checking both Windows and WSL listeners, A started only the missing services with
the exact existing recovery configuration/venvs/model paths. All three launches
were hidden; Chatterbox completed its normal startup/warmup in about106 seconds.

At **2026-11-06 15:45 Europe/Zurich**, `node infrastructure/dev-stack.mjs status`
returned exit0 with **all seven services ready**. This is startup of missing local
processes, not deployment of Calendar/V45, replacement of the running Core or a
live calendar/device test. Logs/PIDs are in the ignored coordination directory.
The recovery helper's own ACL-startup problem remains a separate development-tool
diagnostic; the active services do not depend on it remaining up.

Two newly registered Identity worktrees were also observed during the final
inventory. They were not created, edited, staged, closed or merged by A/B in this
assignment; the owner was asked asynchronously whether another chat owns them.
Do not equate this Calendar source closeout with completion of that separate work.

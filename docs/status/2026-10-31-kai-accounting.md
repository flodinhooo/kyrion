# K-AI durable accounting and acceptance preparation

Date: 2026-10-31. Starting branch/revision: `master` / `c596fc3`.
This continues [the earlier295-test resume](2026-10-31-kai-resume.md).
The pre-existing Calendar/HA worktree remains dirty and untouched; Spaces and
K-Data worktrees remain present. Initial uncommitted changes from the earlier
K-AI resume are this same agent's work and are preserved in this delivery.

## Verified integration and changes

Code inspection confirms the integrated M01 registry/adapters/normalized stream,
M02 deterministic router/preferences/policy/reservations, and M03 account-scoped
ContextBuilder/memory/calendar/unknown-speaker restriction. The original handoff's
red integration baseline and V33 inventory are historical; combined integration
and the verified V39 database upgrade already superseded them.

Implemented under [ADR 0034](../adr/0034-durable-ai-usage-finalization.md):

- A committed invocation fence prevents replay of the same prepared generation,
  including service recreation. Only demonstrably uninvoked attempts can release.
- Additive V40 stores original token/cost and price snapshots plus invocation
  time. Legacy pending attempts become uncertain without inventing prices.
- Complete server-observed terminal usage can reconcile uncertain/estimated
  attempts once. Original month/rates remain fixed; duplicate finalization is a
  no-op. Audit and accounting share the transaction and request correlation.
- Timeout, disconnect, absent completion, missing/partial/invalid/decreasing
  usage and observed overruns retain conservative accounting. Extra unpriced
  categories remain unknown. Conflicting final reports produce one persistent
  `USAGE_CONFLICT` case, rather than silently overwriting/refunding usage.
- Current-period unknown prices and currency changes block monetary-limited
  generation. Mixed SQL aggregates do not hide unknown costs as zero.
- Own usage now exposes accounting state, monetary basis and up to100 open cases
  across all months, with a truncation indicator. Reported tokens with unknown
  money remain open. Web renders DE/EN explanations and handles the older API
  explicitly without claiming that its missing details are complete.

The previous single-period capture and idempotent audit fixes are retained.
Core still owns consent, budget, authority and account/Space isolation. There is
no browser refund/totals API, no new dependency, no billing-only generation retry,
no enterprise retrieval enablement or native tool execution loop.

## Verification and runtime boundary

Final verification:

| Check | Result |
|---|---|
| Full Core suite / `bootJar` | **306 tests, zero failures/errors/skips; build passed** |
| AI pytest / Ruff / format / compilation | **166 passed**; lint,42-file format check and compilation passed; one existing TestClient deprecation warning |
| Web tests | **199 tests /60 files passed** |
| Web TypeScript / ESLint / production build | Passed after regenerated route types; isolated build directory |
| Voice Satellite software | **56 passed**; includes the six session/turn operator-probe tests, also rerun separately; Ruff and compilation passed |
| Infrastructure development checks | **27 Node tests passed** |
| Real local Gemma HTTP chat | `OK.`,833 input /3 output tokens, normalized completion, no error |
| Local readiness / current runtime migration gate | All seven ready; active V39 artifact matches39 installed migrations |
| Read-only Pi network probe | **Blocked**: DNS/config/model/user services/Gateway present; TCP8080 timeout; no physical audio test |
| Whitespace / tooling limits | `git diff --check` passed. Core has no standalone Kotlin formatter/linter task; existing compiler warnings remain. IDE inspections cannot analyze these excluded content roots. |

Relevant commands:

```powershell
$env:JAVA_HOME=(Resolve-Path '.run/dev-recovery/toolchain/jdk-21.0.13.0.2+1').Path
& services/core/gradlew.bat -p services/core test bootJar --offline --console=plain --no-daemon --max-workers=2 `
  '-Pkotlin.compiler.execution.strategy=in-process' '-Pkotlin.incremental=false' `
  "-Dorg.gradle.java.installations.paths=$env:JAVA_HOME"
& services/ai/.venv/Scripts/python.exe -m pytest services/ai/tests -q
& services/ai/.venv/Scripts/python.exe -m ruff check services/ai/src services/ai/tests
& services/ai/.venv/Scripts/python.exe -m ruff format --check services/ai/src services/ai/tests
# apps/web: pnpm test; pnpm exec tsc --noEmit; pnpm lint
# Isolated Web build: KYRION_BUILD_DIRECTORY=.next-kai-accounting-build; pnpm build
# Satellite tests: PYTHONPATH=services/voice-satellite/src, then use existing AI venv pytest
node --test infrastructure/dev-*.test.mjs
```

The new PostgreSQL tests exercise stream faults, late/concurrent settlement,
service recreation, original-month reconciliation, stored pricing despite profile
changes, audit rollback, prepared-generation replay, partial overruns, conflicts,
unknown currencies/prices and own-account/foreign-Space inspection. A disposable
V39→V40 upgrade fixture verifies conservative legacy-state preservation.

The first direct TypeScript check found a malformed generated `.next/dev` route
declaration. The isolated production build regenerated valid types; the following
direct TypeScript check passed. Only the build's two automatically added tsconfig
include entries were removed, preserving the original config. No source-level
TypeScript failure was hidden. An operator-probe test command initially referenced
nonexistent infrastructure test filenames; the real tests are in Satellite tests
and were run. The local smoke script initially assumed `totalTokens` was mandatory;
Ollama reports input/output, and Core correctly derives their total. The probe
was corrected to the actual contract and passed.

Actual runtime evidence: seven local services ready; real AI→Ollama Gemma4b HTTP
generation returned `OK.`, input833/output3 tokens (derived total836), model/text/
usage/completion events and no error. This is local-provider evidence, not live
deployment of the new Core ledger. The running immutable V39 Core artifact still
passes the39-migration compatibility gate with no pending/mismatched versions or
active sync leases. No runtime was replaced, no V40 migration was applied to the
active database and no host/WSL/Docker restart/reset or persistent-data deletion
was performed during this continuation. The earlier resume's WSL/Docker outage
remains separate historical operational evidence; no recurrence is inferred from
product tests. Candidate build output must not be selected for live startup until
a separately controlled backup/migration rollout is authorized.

## Open items and acceptance handoff

- **Code / KAI-005:** durable automatic provider invoice lookup/attribution and an
  operator resolution API are not implemented. Current adapters do not retain a
  provider billing identifier suitable for crash recovery. Unattributable,
  disputed or historically unpriced attempts remain visibly open; no SQL refund
  or paid replay is an accepted workaround. Cost/token estimates remain estimates.
- **Cloud / KAI-004:** no spending authorization and no configured/enabled cloud
  provider in the running catalog. No paid call or key provisioning occurred.
  The [concrete provider/model/budget plan](../kai-accounting-and-acceptance.md#cloud-acceptance-plan--not-executed)
  remains unexecuted, with official sources and explicit success/stop criteria.
- **Hardware / KAI-003:** physical wake/capture/STT/K-AI/TTS/PipeWire playback,
  speaker identity and real-room latency remain unaccepted. The
  [Pi checklist](../kai-accounting-and-acceptance.md#practical-raspberry-pi-velora-checklist--physical-acceptance-open)
  specifies20 DE/EN trials, median/p95 and safe fault diagnosis. Core's loopback
  bind still requires a separately reviewed LAN path before Pi-to-Core testing.
- **Operations / KAI-002:** V40 backup/restore and controlled rollout are open.
  The previously observed WSL/Docker instability and desktop Ollama junction-path
  recurrence are not claimed fixed by ledger work. Do not restart the helper or
  select a candidate JAR just to perform acceptance; retain guarded boundaries.
- **Other gates:** KAI-006 shared/enterprise isolation, native tool continuation
  and unrelated Spaces/Knowledge/physical-device acceptance remain unchanged.

Only this agent's enumerated changes are intended for the delivery commit;
the nested Calendar worktree, runtime state/logs, credentials and generated build
outputs are excluded. No push or deployment is part of this delivery. The commit
is discoverable with `git log -1 -- docs/status/2026-10-31-kai-accounting.md`.

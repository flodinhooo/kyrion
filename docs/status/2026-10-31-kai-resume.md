# K-AI resume: accounting consistency and local runtime

> Later continuation on the same day: [durable accounting and acceptance preparation](2026-10-31-kai-accounting.md).
> The295-test/runtime checkpoint below is historical evidence for the first resume;
> the later report records the expanded ledger and its own verification without deployment.

Date: 2026-10-31. Starting revision: `c596fc3`. Scope: K-AI only; the pre-existing
dirty Calendar/HA worktree is preserved. No cloud request, new dependency,
migration or physical Voice/device acceptance is part of this change.

## Reconciled work order

The original K-AI handoff records M01 provider adapters, M02 Core routing/policy/
usage and M03 personal context. Its red combined baseline is superseded by the
[final integration](../integration/final-integration-report.md): KAI-001 was
resolved with all four streams integrated. The verified
[real-data V33-to-V39 upgrade and restore rehearsal](../integration/database-upgrade-v39.md)
also supersedes the original operational inventory. Neither record certifies
new live cloud, physical Voice or shared enterprise retrieval.

This continuation addresses a bounded part of **KAI-005**, rather than treating
an administrative refund/reconciliation API as already specified or authorized.
The remaining KAI-002 runtime rollout and KAI-006 isolation gates are distinct
from the completed database migration and combined software baseline.

## Behavior change

- Usage summaries capture one UTC month for both their label and counters.
- Reservations capture one UTC month after acquiring the existing account lock;
  budget checks and insertion use the same period across midnight.
- Settlement and uninvoked release emit completion audit events only when an
  owned pending attempt actually changes. Repeated or racing callbacks cannot
  create duplicate completion evidence, refund finalized attempts or affect a
  foreign account's attempt.
- The existing conservative pending/uncertain charge policy remains in force.
  No automatic refund, replay, new authority or administrative API is introduced.

Changes are in `AiSettings.kt`, five new isolated `AiUsageServiceTest` cases and
two PostgreSQL-backed tests in `AuthenticationPersistenceIntegrationTest.kt`.
The orchestration guide documents period and finalization behavior. Startup/TODO
documentation now points to the integrated implementation and V39 evidence,
instead of presenting the older provider review/V33 state as current.

## Verification

Full Core `test bootJar` passed: **295 tests, zero failures/errors/skips**.
This includes concurrent settlement, duplicate release, foreign-account and
month-boundary regressions. Java21 and the existing Gradle cache were used;
the successful run used `--offline --no-daemon --max-workers=2`, in-process
Kotlin compilation and disabled incremental compilation. An initial test
compilation error in the new JDBC mock's nullable UUID type was corrected
before the full passing run. Existing compiler deprecation/nullability warnings
remain. No AI/Web source changed; their historical full-suite results are not
reported as rerun results.

The new test file was passed through IDE formatting. IDE batch inspections
could not analyze these files because they are outside the current IDE content
roots; compiler/test checks passed instead. No configured standalone Kotlin
lint/format task exists in Core. `git diff --check` is part of the final check.

## Runtime evidence and limitations

The first status probe found only Ollama ready. The existing bounded startup
workflow recovered PostgreSQL, Web, Core, AI, STT and TTS. PostgreSQL performed
several minutes of recovery; its existing data/container were preserved. All
seven local readiness checks subsequently passed. The helper also started its
already configured Pi user units; that is not acoustic or device acceptance.

Real AI HTTP generation initially failed with `MODEL_UNAVAILABLE`: the running
desktop Ollama had an empty model catalog and `bad manifest` path errors.
All existing Gemma/Qwen manifests and Gemma4b blobs were present. A separate
loopback-only diagnostic runtime with the direct `E:\Ollama\Models` path found
all three models. The desktop runtime and diagnostic process were then replaced
by one loopback-only runtime on11434 using the direct path, cloud disabled and
pruning disabled. No weights were downloaded or deleted. Real HTTP Gemma4b
generation then passed with model/text/usage/completion events and no error.

The recovery settings initially selected the older V33-only Core artifact. The
newly tested integrated artifact passed the read-only compatibility gate against
all39 installed migrations, with no pending/mismatched versions or active sync
leases. A local settings backup was retained before selecting this artifact.
Operational rollout and the final readiness result are recorded below.

The helper reload briefly failed on the Windows-written JSON file's UTF-8 BOM;
rewriting that local settings file without a BOM corrected it. During the helper
replacement, AI/WSL/Docker availability was lost again. This is a temporal
observation, not a demonstrated root cause for the host's existing instability.
The next helper job initially failed its database/Core stage while Docker was
recovering, then recovered AI/STT/TTS. No WSL shutdown, Docker reset or data-volume
deletion was used. After SQL readiness returned, the reviewed Core artifact was
started from a separate immutable copy with Java21 and a process-only loopback
bind. Flyway validated39 migrations and applied none.

Final `node infrastructure/dev-stack.mjs start` returned exit0 with all seven
local services ready. A second real AI HTTP Gemma4b generation passed after this
rollout; the running immutable Core copy also passed the39-migration compatibility
gate. Core is intentionally external to the newly launched helper's managed
process map, so helper restart preserves it; stop it deliberately before a future
artifact replacement. Local logs/settings backup/immutable artifact are under
the ignored `.run/dev-recovery/kai31/`. Recovery settings select the current
primary-checkout build for future starts. No LAN exposure or firewall change was
performed, so this establishes local development readiness only. Satellite
service activity does not establish Pi-to-Core connectivity or physical Voice.

## Remaining work

KAI-005 remains **partially addressed**: trusted reconciliation of uncertain
provider usage, crash recovery and provider-cost evidence remain open. Unknown
outcomes retain their reservation. Spending approval/credentials for KAI-004,
speaker identity/physical Voice for KAI-003 and exhaustive shared-context
isolation for KAI-006 remain separate gates. The host's documented WSL/Docker
instability and desktop-autostart model-path recurrence are operational follow-up.

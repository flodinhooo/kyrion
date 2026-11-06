# Gateway acceptance and rollout preparation

Status: source implemented, verified and committed; real rollout/hardware gates
remain open. This follow-up extends Assignment B;
it does not deploy the earlier `c398402` / `fba7cbb` source delivery.

## Scope, starting state and coordination

Read AGENTS, README, the complete two-chat ownership handoff, previous B results,
authority design, Gateway hardware/provisioning and current TODO/Pi activation,
hostname recovery, backup and Windows/Pi startup documents. Actual checkout was
`master` at `fba7cbb`, containing A's `69cee10` V43 work. A is implementing HOME-03
in Calendar/Google/Web and reserved ADR 0037/V44. B neither edited nor staged
those files. No new migration, branch or worktree is needed for this task.

Coordination uses the existing ignored `gateway-B-status.txt` and
`home-A-status.txt`. A froze Core for the diagnostic; B released it for A's last
regressions; both then froze Core for the combined acceptance. The new runner
holds the existing exclusive `core-checks.lock` throughout test/build and records
before/after hashes of all Core sources/resources/tests/build configuration.
Git mutations use the separate exclusive `git.lock`, an empty-index check,
explicit owned paths and staged-diff validation. No shared overview or
authentication/RBAC/Voice/build configuration was changed by B.

The native shell tool did not respond at session start; IDE file/terminal tools
provided the working repository connection. `rg` was unavailable in that shell;
Git file inventory and PowerShell text searches were used. No runtime recovery
action was used to restore tool access.

## Fresh read-only runtime evidence

At 2026-11-06 12:58:39 UTC, with no starts/restarts or configuration changes:

| Observation | Result |
| --- | --- |
| Windows database | `kyrion-postgres`, all migrations successful through V39. Queue: 290 succeeded, 115 failed; no pending/running rows. |
| Windows Core | Later direct loopback 8080 health read returned UP. An earlier listener inventory returned no rows; runtime readiness is an observation, not an invariant or evidence of new-code activation. |
| Pi database | All migrations successful through V41. Queue: 309 succeeded, 130 failed; no pending/running. Three button-binding rows; zero active Calendar sync leases. |
| Pi Gateway | Service active, recorded start 2026-10-19. One database node heartbeat, age 3.48 seconds. |
| Pi Core | Healthy `kyrion/core:0eb44f6-deployfix`, image `f7f4038145b69714a15af5b6ed03ae2a8469937d7603a0beab416a9df8604c04`. Loopback 18080 health 200/UP; unauthenticated `/v1/devices` 401. |
| Pi Web | Healthy `kyrion/web:0eb44f6`, image `77ccb71fa8bf63d390baca20cc707e2697550308c2b20e80117d5b476ea0e281`. Windows HTTPS hostname login 200 with normal certificate trust. |
| Remaining protected inventory | Gateway agent JSON/destination and installed Compose are not readable by the SSH account; `sudo -n` unavailable. Existing non-sudo Docker access did permit image and read-only SQL inventory. No privilege/configuration change or secret export was attempted. |

Only health/denial GETs, service/image metadata and fixed SQL SELECTs were used;
SQL inventory ran read-only transactions. No live queue claim/result/button or
Voice session endpoint was called. The protected credential-bearing config was
not printed. Ignored local metadata record:
`.run/dev-recovery/coordination/gateway-runtime-evidence.jsonl`.

The current Pi schema/images confirm the latest activation report. Older Gateway
README/provisioning text describing Windows as the target cannot establish the
installed agent destination; that remains an operator check. V42/V43 are still
not activated on these observed installations.

## Proven defect and fix

The new legacy-array-payload regression failed before the fix with
`MismatchedInputException`: the queue row mapper decoded payload before checking
authority. For a malformed historical row with NULL/unreadable provenance,
`next` rolled back its claim before producing the intended terminal denial.
Repeated polls could keep selecting that row and block subsequent commands.
This was reproduced with isolated synthetic data; no live malformed row is claimed.

`GatewayCommandRepository.claim` now reads provenance first. If it is missing or
unreadable, it does not interpret the historical payload; the existing mandatory
service check records `AUTHORITY_PROVENANCE_MISSING`, failure and correlated audit
without returning a payload. Authorized rows retain their existing typed parsing
and validation. The regression checks zero release, terminal/audited denial and
successful claiming of a subsequent valid member command. No permission bypass,
automatic grant or migration is introduced.

## Reproducible acceptance and actual rollback boundary

- New `GatewayRolloutRehearsalTest`: disposable Testcontainers PostgreSQL only;
  actual V41 custom-format dump and two restores, candidate-only V42/V43 migration,
  retained command/correlation/ciphertext/binding markers, no manufactured
  provenance/grants, unchanged original source and independently valid V41 restore.
- In that same disposable candidate the exact historical claim SQL releases the
  old pending row despite absent authority. Default Flyway validation with only
  V1–V41 resources accepts the later history. This is a library/SQL compatibility
  proof, not a claim that a complete old production image was launched. It proves
  why an old binary against the upgraded database is not a safe authority rollback.
- Post-V43 synthetic household data is preserved in the candidate while absent
  from the pre-upgrade restore: full restoration requires explicit reconciliation
  of writes after the backup. Original keys/documents and external effects are
  outside a SQL-only restore's guarantee.
- New `Test-GatewayRollout.ps1`: selected Gateway acceptance or `-FullCoreSuite`,
  JDK 21/native-exit validation, forced fresh tests+bootJar, exclusive Core lock,
  source manifests, required-suite and zero-skip assertions, JAR SHA256 and exact
  migration inventory. No live target parameter, application launch or deployment.
  `rolloutAuthorized` is always false; migrations above the V43 rehearsal target
  are explicitly listed instead of being silently included in release approval.
- New stdlib Python gate tests: six synthetic-JAR cases verify existing Windows
  runtime gate rejection across V41/V43 and V43/V44 in both directions and active
  Calendar leases. They mock SQL and make no Docker/provider request.

Reproduce from root:

```powershell
python -m unittest discover -s infrastructure/dev -p test_gateway_rollout_gate.py -v
& infrastructure/dev/Test-GatewayRollout.ps1 -JavaHome '<existing JDK 21 directory>'
& infrastructure/dev/Test-GatewayRollout.ps1 -JavaHome '<existing JDK 21 directory>' -FullCoreSuite
```

Diagnostic history: first launcher attempt failed before compilation because
`--tests` followed `bootJar`; runner argument order was corrected. The real
diagnostic then ran 29 tests: 28 passed including the new dump/restore rehearsal;
only the intended legacy malformed-payload regression failed. Its source
manifests were unchanged. Evidence is under ignored
`.run/dev-recovery/gateway-acceptance/bab74f172ac84801993d5f68e47557e5/`.

Python unit tests: six passed. Ruff check and format check passed for the new
Python test. PowerShell AST parsing passed. Final combined Core results, artifact
inventory, source stability and commit IDs are recorded below.

## Operator plan and still-open acceptance

[The new runbook](../gateway-authority-rollout.md) separates Windows V39 and Pi
V41, exact artifact/migration review, quiescent backup boundaries, original keys/
Knowledge/configuration, isolated restoration, migration-only apply preparation,
startup pins/Compose, HTTPS/heartbeat checks and per-button explicit resave. It
distinguishes V43-compatible authority-aware fallback from full pre-upgrade
restoration, and forbids old V39/V41 binaries against V42/V43 or ignored V44.
An old-runtime restore also restores the old authority gap; keep action ingress
disabled rather than calling that a security-preserving operational rollback.

Reviewed existing tools include runtime compatibility/startup gates, SQL backup/
restore verifier, platform preflight, initial-install bundle, unconditional agent
update script and radio file snapshot. The runbook records why fresh-install
transfer and unconditional agent restart are unsuitable shortcuts for this update.

Open before a real rollout: protected original-key/document restore drill on each
installation; current agent destination confirmation; reviewed exact release
artifact and all included migrations (A's V44 is separate); reviewed migration-only
apply command; rechecked work/leases and an approved maintenance window; explicit
human review/resave of the three observed old Pi bindings. No SQL-generated or
bulk automatic grants. The runbook does not claim an existing safe general updater.

Open hardware acceptance: real single/double/long button actions and exact room/
device/multi-provider/offline outcomes, HOME Voice sessions, gateway restart and
network reconnect, late results, OA20 telemetry/reconnect, original radio restore
on a disposable fixture and full-host cold start. These require separately
authorized hardware/maintenance windows and human visible/audible verification.

No deployment, production migration, runtime restart, provider write, device
action, private-backup export or automatic legacy binding approval occurred.

## Final verification and commits

Final reproducible runner result:

- `Test-GatewayRollout.ps1 -FullCoreSuite -JavaHome <existing JDK21>`:
  **386 tests**, zero failures/errors/skips; fresh compilation, full test suite
  and `bootJar` succeeded in **3m 52s** with `--rerun-tasks`.
- GatewayAuthorityIntegrationTest **28**, GatewayRolloutRehearsalTest **1**,
  HouseholdCalendarIntegrationTest **10**, PersonalCalendarDisclosureIntegrationTest
  **13**, GoogleCalendarHttpTest **5** all pass, alongside the remaining Core suites.
  A independently owns HOME-03/Google code and its final Web acceptance.
- Before/after Core source manifests are identical; tested base HEAD before and
  after was `fba7cbb81e9d1416a595f2367d761be7c604eee5`, plus the frozen A/B working
  sources. Source contents were rechecked against that manifest before B commit.
- Evidence directory:
  `.run/dev-recovery/gateway-acceptance/1c0f114f29f9410c9a4124c1dd482054/` contains
  `evidence.json`, `gradle.log`, `source-before.json`, `source-after.json`.
  The machine report has `passed=true`, `gradleExitCode=0`, `javaMajor=21`, no
  changed Core files, and `rolloutAuthorized=false`.
- Built JAR SHA256:
  `0cf25019380fb38486f87d830cd0b7c918860865c32cdc2891879abf10f308a5`.
  Its catalog is V1–V44, explicitly reporting `[44]` beyond the V43 rehearsal.
  It is **not** the V43-only release artifact and was not started or deployed.
- Python gate **6** tests pass; Ruff lint/format and PowerShell AST parse pass;
  explicit staged `git diff --check` passes. Core has no dedicated configured
  formatter/linter; Kotlin/Java compilation is its type-checking evidence. No
  dependency or Core build configuration was added.

Commit **`157a399588dd8aa975cd877fd131e49df7faf5b1`** contains exactly the seven
implementation/test/tool/runbook paths below, excluding this report. No A-owned
Calendar/Google/UI/ADR0037/V44/overview or private file was staged. A independently
committed HOME-03 as `1ed89e157365ec48b30e6d5271d618709ad5a55b` before B's Git window;
therefore B commit `157a399` naturally has that parent and contains V1–V44 in its
complete source tree. This was checked with `git ls-tree`, not inferred from the
seven-file B diff. It is **not a V43-only source candidate**. Either include V44
in an explicitly reviewed release/rollback scope with A, or separately prepare
and test an approved Gateway-only backport on the earlier V43 baseline. Do not
strip V44 SQL from newer code, switch branches or rewrite this shared history to
manufacture a candidate. `fba7cbb` remains the earlier V43 source baseline, with
the now-documented malformed-legacy-payload defect; no new V43-only fixed binary
was built here. No release image, signature or production migration-only
mechanism was produced in this task.

This report is a separate documentation commit. Resolve its exact ID with
`git log -1 -- docs/agent-handoffs/2026-11-06-gateway-rollout-results.md` or the final
chat delivery. Both Git mutations use the exclusive Git lock, an empty index,
explicit filenames and full staged-path validation. The final source manifest
still applies when A later commits its unchanged tested source.

B-owned paths:

```text
services/core/src/main/kotlin/dev/kyrion/core/gateway/GatewayCommand.kt
services/core/src/test/kotlin/dev/kyrion/core/security/GatewayAuthorityIntegrationTest.kt
services/core/src/test/kotlin/dev/kyrion/core/security/GatewayRolloutRehearsalTest.kt
infrastructure/dev/Test-GatewayRollout.ps1
infrastructure/dev/test_gateway_rollout_gate.py
docs/gateway-command-authority.md
docs/gateway-authority-rollout.md
docs/agent-handoffs/2026-11-06-gateway-rollout-results.md
```

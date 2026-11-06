# Two-chat ownership: Home calendar and Gateway authority

Status: prepared assignment, not an assertion that a second chat is running.
Baseline: master `8b9f2d4`; verify current HEAD/status before editing.
The user will explicitly start the second chat. No agents are spawned by this plan.

## Assignment A: this chat

Own Home/Calendar planning and implementation following ADR 0035 and HOME-01 onward.
Own `docs/home-family-calendar-plan.md`, ADR 0035, `calendar/**`, calendar Web
features/routes/locales, and calendar-specific tests. Coordinate before changing
Google integration code because it contains personal credentials and shared APIs.
Do not edit Assignment B's paths during concurrent implementation.

## Assignment B: second chat

Deliver the bounded Gateway queued-command authority P0. Read README, AGENTS,
the current source, `docs/gateway/architecture.md`, `docs/rbac.md`, the Spaces
hardening handoff and this file before deciding architecture. Write ADR 0036 for
the concrete authority/persistence design before implementation. Core owns all
authority; adapters, model output, browser owner IDs and payloads cannot supply it.

Required result:

- Capture the original authenticated human separately from the resource Space,
  required permission/capability and correlation when enqueuing. Preserve that
  explicit principal through claim/dispatch/retry; revalidate current membership,
  enabled state, Space and permissions before releasing a command to the gateway.
- Never infer OWNER authority for historical pending rows lacking provenance.
  Use an explicit fail-closed compatibility disposition and truthful status/audit.
- Model explicit, bounded integration/automation authorization for non-human
  commands. Revalidate grant lifecycle and binding scope; node credentials or a
  resource-owner UUID alone must not imply a human's authority. Preserve the
  supported HOME Voice path using an explicit reviewed device/session authority;
  do not enable Business Voice or label a satellite as an identified human.
- Inspect all enqueue/await/execute callers, including device commands, direct
  gateway routes, Zigbee/Bluetooth discovery/management, room/device removal,
  YouTube playback and Action Orchestrator. Avoid adding an optional actor
  argument that production callers can omit to bypass validation.
- Preserve ownership predicates, typed contracts, policy/confirmation, bounded
  execution, audit actor/Space/correlation, conservative outcomes and retry rules.
- Test a valid member; role/membership/session changes as applicable; disabled or
  foreign principals; suspended Space; deleted/reconfigured bindings; revoked
  automation grants; cross-node/Space claims/results; legacy provenance absence;
  retry and duplicate-claim behavior. Tests must assert zero dispatch on denial.
  Full device-side acceptance remains separate from synthetic tests.

Owned implementation paths, including their focused tests:

- `services/core/src/main/kotlin/dev/kyrion/core/gateway/**`
- `.../action/ActionContracts.kt`, `ActionEndpoint.kt`, `ActionOrchestrator.kt`
- `.../capability/DeviceCommand.kt`, `.../automation/ZigbeeButtonBinding.kt`
- `.../home/RoomController.kt`, `.../integration/YouTubeIntegrationController.kt`
- Gateway/action/automation/device-command unit tests and a new dedicated
  `security/GatewayAuthorityIntegrationTest.kt` (do not append to the large shared
  `AuthenticationPersistenceIntegrationTest.kt`).
- New additive migration **V42**, reserved exclusively for Assignment B;
  recheck that it is unused before creating it. Never rewrite an existing version.
- ADR **0036**, `docs/gateway-command-authority.md`, and
  `docs/agent-handoffs/2026-11-06-gateway-authority-results.md`.

## Shared paths: no uncoordinated edits

Neither chat may silently edit `Rbac.kt`, `TenantBoundary.kt`, authentication,
`AuthenticatedRouteInterceptor.kt`, the shared authentication integration test,
Core build configuration, AI orchestration, Voice code, root AGENTS/README,
`docs/status/TODO.md` or this ownership file while the other chat is implementing.
If an essential change falls outside owned paths, write the exact proposed
contract/diff and reason in the chat-specific results/handoff and report the
dependency to the user. Continue independent work. Do not weaken checks to avoid
coordination. Assignment A will integrate shared documentation updates later.

Assignment A reserves new calendar migrations **V43 and later**, rechecking actual
history first. Do not ship/deploy them before V42 is settled. Do not create dummy
V42 files or renumber migrations another chat has already created/applied.

## One-checkout coordination rules

Both chats use the primary checkout on **master**. No branches, worktrees, resets,
stashes, force operations, pushes, deployment, runtime restarts, schema upgrades,
real device actions or paid provider calls as part of this assignment. A separate
checkout would require a new explicit user decision. Separate paths reduce edit
conflicts but cannot make a shared Git index/build directory fully isolated.

Use cooperative exclusive file locks under the ignored `.run/dev-recovery/coordination/`:
`git.lock` for all Git index/ref mutations; `core-checks.lock` for the entire Core
compile/test/build operation. These are persistent lock files, not Git's own
`.git/index.lock`. Both chats must follow the protocol. Acquire a lock by holding
an open .NET FileStream with `FileShare.None`; close it in `finally`. Do not delete
or steal lock files; an OS-released handle is sufficient after process exit.
If busy, continue other owned work and retry later. Do not nest the two locks.

Example PowerShell acquisition (keep the action in the same process):

```powershell
$lockDirectory = Join-Path (Get-Location) '.run/dev-recovery/coordination'
New-Item -ItemType Directory -Path $lockDirectory -Force | Out-Null
$heldLock = [System.IO.File]::Open(
    (Join-Path $lockDirectory 'git.lock'),
    [System.IO.FileMode]::OpenOrCreate,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None)
try {
    # Inspect staged paths before staging; if another task has staged content,
    # release the lock and report it. Never unstage or commit that content.
    # Stage explicit owned paths, inspect staged diff/check, then commit.
    # Never use git add ., git add -A, commit -a or amend.
} finally { $heldLock.Dispose() }
```

For Core checks use the same pattern with `core-checks.lock`, repository-root
absolute paths and `Push-Location services/core` inside the protected operation.
Native command failures must be checked and propagated; locking is not validation.
The lock coordinates build commands, not arbitrary simultaneous source edits:
record tested HEAD and owned diff; rerun affected checks if relevant source changed
during verification. Both chats should announce their check window and avoid
editing Core during the other's full acceptance run. If a stable window is not
available, report provisional results and leave final combined acceptance to A.

## Delivery by B

Finish a complete reviewed source slice within the owned boundary and commit only
its files under the Git lock after validation. Run proportionate regression tests,
full Core test suite and bootJar under the Core lock. Inspect configured formatter,
linter/type-check tasks; report unavailable checks. Do not add dependencies unless
necessary and explained. Report exact commits, files, tests, migration and caller
coverage, remaining coordination dependencies and non-deployment status in the
results file. Do not mark P0 closed if any production enqueue path still bypasses
authority or the complete change cannot be validated within the agreed boundary.

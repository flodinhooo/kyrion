# Master consolidation and worktree closeout

Date: 2026-11-06. The owner requested that development continue on `master`,
including all existing commits and unfinished worktree changes.

## Branch cause and integration

The reflog records `master` -> `fix/spaces-hardening` on October 31 at 18:18:26
Europe/Zurich. The November 6 service-start session inherited that branch.
`master` was fast-forwarded from `bdd6f83` to `bb566e8`, preserving the three
Spaces hardening commits and the deployment/activation commit.

The five V39 compatibility commits were merged in `0402c77`. Their eight changed
files already had equivalent fixes on master; conflicts retained the newer
durable usage invocation fence and Voice/session/security regressions. No V40/V41
migration was removed to mimic the older runtime branch.

Calendar/HA's 62 modified/untracked files were preserved in `70bda97` before
merging in `31189ee`. Forty-five files were byte-identical to primary; seventeen
differed because primary had later security, Calendar DELETE, configuration,
tests and documentation. The merge retained these later versions and adopted
the useful README links. Canonical applied migrations remain unchanged.

K-Data `25b6fee` and Spaces `024e1e6` were already ancestors of master. All four
former worktree branch tips are now ancestors of master; no branch was reset,
force-pushed or deleted. No remote publication was performed.

## Worktree cleanup and preservation

The three accidentally tracked `.worktrees/*` gitlinks are removed from the
primary index. `.worktrees/` is ignored as local development state. This removes
the misleading dirty-submodule entry that repeatedly prevented empty commits.

The dirty Calendar files, checksums and binary patch were first copied into the
protected ignored `.run/dev-recovery/worktree-closeout/` directory. Git bundles
retain history before and after integration. Worktree removal encountered
Windows long-path/nonempty-directory failures after unregistering three trees;
their remaining directories were moved intact to `retired-checkouts/` beneath
that protected archive instead of deleting ignored configuration/build data.
The clean V39 tree was removed normally. Only the primary master checkout remains
registered. Retained archive files are not active worktrees or project source.

The root agent instructions now record the owner's master-only workflow and
prohibit accidental worktree gitlinks. This does not authorize automatic pushes.

## Remaining product work

Two bounded security follow-ups were implemented on master:

- The HTTP AI transport periodically revalidates captured authority even when
  the provider sends no response headers or only a partial event. Denial cancels
  the request/body instead of waiting for the provider's next event. Synthetic
  HTTP tests cover both silent states, frame handling, downstream cancellation
  and the existing total deadline.
- Queued Zigbee button work reloads the binding and validates that its button
  still exists before target resolution. Deleted/reconfigured bindings cannot
  execute their captured old action; unchanged bindings still enter the shared
  Action Orchestrator once. This is not the missing persisted integration grant
  or originating-human authorization through the downstream Gateway queue.

Source integration and worktree closure do not certify every historical TODO.
The original handoffs remain evidence; this record supersedes their outstanding
branch-integration instructions. The Pi activation and local-hostname recovery
records also supersede the earlier V30/sudo/DNS blockers:

- [Pi V41 activation](2026-11-06-pi-update-activation.md).
- [Local Web hostname recovery](2026-11-06-local-web-name-recovery.md).
- [Spaces hardening security priorities](../agent-handoffs/spaces-hardening-handover.md).
- [Combined TODO dispositions](../integration/final-integration-report.md).

Gateway originating-principal queue/dispatch authorization and explicit automation
grants remain P0 implementation work. Full stream/context/cache/worker lifecycle
certification remains P0; individual regressions do not certify all of it.
Real embedding/RAG, complete document recovery, Business SMTP/DNS/interactive
recovery, clean-room installer release and physical Voice/device/Calendar checks
remain distinct acceptance work. Paid cloud calls, destructive reboot drills and
audible hardware acceptance are not implied by source integration.

## Final verification

- Core: **332 tests**, zero failures/errors/skips; `bootJar` passed. The preceding
  run failed only during startup of the disposable PostgreSQL fixture at its
  default 60-second log-readiness deadline; the full rerun after parallel builds
  completed passed, including all 88 authentication/persistence integration tests.
  No wait strategy, assertion or production database was weakened to obtain a pass.
- Web: **200 tests**, ESLint, TypeScript and production build passed. Build output
  used `.next-master-closeout-build` to preserve the active dev server. Next's
  generated tsconfig additions were removed after validation.
- AI: **172 tests**, Ruff lint and formatting passed. One inherited formatting
  deviation in the experimental Qwen runtime was normalized; before/after Python
  ASTs are identical. No speech runtime or model configuration was changed.
- `git diff --check` passed. Core has no separately configured formatter/linter.
- All seven local service readiness probes passed after verification. These
  source fixes were built/tested, not deployed over the pinned Windows V39 or Pi
  runtime by this consolidation. No migration, paid provider request, hardware
  action or host reboot was performed.

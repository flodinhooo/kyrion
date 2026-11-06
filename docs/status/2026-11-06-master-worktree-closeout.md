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

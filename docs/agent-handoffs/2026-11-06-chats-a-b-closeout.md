# Chats A and B: consolidated closeout for Identity integration

This is the durable handoff allowing both Calendar/recovery chats to close.
Snapshot: 2026-11-06, primary checkout `E:/dev/Kyrion/kyrion`, branch `master`,
clean before this documentation change, source HEAD `e93ae7b`.
This document's own commit is discoverable with `git log -- <this-file>`.
Source completion, local service startup and operational activation are separate.

## Product decisions to preserve

- Prioritize private households. Business verification and Business Voice are
  later scope, not completed features. Household and Business account types must
  remain isolated; a private account must not gain Business access.
- First installation establishes its Space and owner; the owner assigns roles.
  Multiple household installations are a stated future identity use case, not
  proof that cross-installation membership already works.
- Kyrion provides a shared family calendar. Selected participants can both edit
  a shared event; deletion remains creator-only in the implemented slice.
- Personal calendar disclosure is voluntary and connection-bound: PRIVATE,
  AVAILABILITY or DETAILS. Destination consent is separate from read disclosure.
- Sending a shared event to selected personal Google calendars requires each
  destination owner's opt-in and explicit manual publication. Core owns
  authorization, validation and audit; neither UI nor AI bypasses it.

## Delivered on master

| Commit | Chat | Result |
| --- | --- | --- |
| `157a399` | B, earlier scope | Gateway authority rollout rehearsal and malformed legacy-command rejection |
| `ce10573` | B, earlier scope | Gateway findings and remaining rollout acceptance |
| `e3d9ff4` | A | Manual delivery of joint events to selected opted-in personal calendars, V45 |
| `209217a` | B | Artifact-bound schema-only migration tool and independent dump/restore rehearsals |
| `d78e212` | B | Migration evidence and operational acceptance boundaries |
| `e93ae7b` | A | Confirmed own-copy presentation, DST/time preservation and usable Calendar dialogs |

Earlier shared-event and disclosure slices are also present in this master
history. These commits already belong to master: do not cherry-pick them back
onto master or replay their SQL as newly numbered migrations.

Chat A added an authenticated Core endpoint for the current user's confirmed
delivery-copy links. The Web server merges only verified matching own copies;
uncertain, edited, recurring or privacy-restricted entries retain their existing
behavior. Correlation metadata is not exposed to the browser. Unchanged event
times retain exact instants across autumn DST and fractional seconds; invalid
spring-gap edits are rejected. Long dialogs scroll on desktop and mobile.

Chat B's tool reads Flyway/JDBC and migrations from the reviewed, hashed boot JAR
without starting Core, Spring, schedulers or providers. Planning is read-only by
default. Apply binds reviewed plan/artifact/tool/catalog hashes, target identity
and unchanged data/history/sequences. It does not replace a maintenance fence.
Real pg_dump/pg_restore operations used synthetic disposable data for independent
V39/V41/V43/V44 to V45 upgrades, rollback copies and a standalone V45 restore.

## Verification and evidence

- Frozen combined source: **422 Core tests**, zero failures/errors/skips,
  successful compilation and bootJar. This includes A's six copy-link regressions.
- Web: **246 tests**, lint, TypeScript check and production build passed.
- B tooling: **11 offline tests**, six existing gate tests, Ruff/format checks
  and PowerShell syntax checks passed.
- A's isolated two-user browser fixture exercised joint editing, revision
  conflicts, explicit recipients, partial publication failure, disclosure
  revocation, mobile dialogs and DE/EN. It used synthetic accounts and providers;
  it does not establish live Google or hardware acceptance.
- Core/tool source hashes were independently rechecked unchanged before A's
  final commit. Identity integration changes invalidate this as acceptance of
  the newly combined tree: rerun appropriate combined checks after integration.

Reproduce B's complete synthetic acceptance with a local JDK 21:

```powershell
& infrastructure/dev/Test-CoreSchemaMigration.ps1 -JavaHome '<JDK-21-path>' -FullCoreSuite
```

Tracked references are the durable evidence summaries:
[A results](2026-11-06-calendar-usability-results.md),
[B results](2026-11-06-core-schema-v45-results.md),
[first-use readiness](../home-first-use-readiness.md),
[V45 operator sequence](../core-schema-v45-rollout.md),
[Gateway runbook](../gateway-authority-rollout.md),
[product plan](../home-family-calendar-plan.md),
[TODO](../status/TODO.md), [ADR0039](../adr/0039-owned-calendar-copy-presentation.md)
and [ADR0040](../adr/0040-artifact-bound-schema-migration.md).
Ignored local logs are supplementary, not required chat history. B's manifest,
logs and immutable reviewed JAR reside under
`.run/dev-recovery/schema-acceptance/431da2a67e9842beb11a99951e21ae11/`.
That JAR's SHA-256 is
`4dd4928e2dd1e3b4076d073edece4d0b5621b62cc4d4181d14b746c69b77de42`;
it is not an ARM64 release or approval of later source.

## Local runtime and remaining operational work

At 15:45 Europe/Zurich, all seven local services were ready: PostgreSQL5432,
Web3000, Core8080, AI8000, Ollama11434, STT8040 and TTS8020. Only missing AI/STT/TTS
were started with existing configurations; running Core was not replaced.
The standard recovery helper failed during ACL initialization; that diagnostic
remains open. No permissions were weakened to start it. Recheck runtime status
in the next session rather than treating this observation as permanent.

No productive migration, new Calendar deployment, Pi activation, live provider
write or device action was performed by this closeout. Earlier runtime schema
observations were Windows V39 and Pi V41; obtain fresh evidence before rollout.

Remaining acceptance is explicit:

1. Independently restore original data with original credential/audit keys and
   private configuration; preserve revocations, audit histories and later effects.
2. Verify protected Gateway/Voice destinations and actual Windows/Pi identity.
3. Review exact release artifacts and ARM64 provenance; fence writers and follow
   the reviewed schema-only rollout/rollback sequence before runtime activation.
4. Personally review/resave legacy buttons; do not auto-approve them.
5. Accept real calendar-account and hardware behavior using controlled test data.

New providers, Business features, recurrence/all-day authoring, automatic delivery,
provider-copy deletion and a wall-time ambiguity chooser remain separate scope.

## Chat 3: existing Identity worktrees and integration assignment

The following registrations were observed read-only; A/B did not create, edit,
merge or close them. Their dirty state and integration readiness are unassessed:

| Existing checkout | Branch | Observed HEAD |
| --- | --- | --- |
| `.worktrees/identity-integration` | `integration/unified-identity` | `dcc2dee43149c5d67ea632e7e2e362d03641eda1` |
| `.worktrees/unified-identity` | `feat/unified-identity` | `fe25b0d36db0652ce760571c762ca205dff33089` |

The owner now identifies Chat 3 as the continuation for the worktree integration.
Use this assignment without depending on either closed chat:

> Read this handoff, repository AGENTS.md and applicable nested instructions.
> Inventory the primary master checkout and both existing Identity worktrees,
> including uncommitted/untracked source, private configuration, commits and merge
> bases. Preserve all work. Reconcile the Identity changes with current master,
> especially account/Space isolation, participants, consent/destination ownership,
> authorization, audit identity and migration numbering/checksums. Use the existing
> checkouts; do not create or switch the primary checkout away from master.
> Integrate the complete reviewed source into master, resolve conflicts explicitly
> and run relevant combined tests/builds. Record final commits, test evidence and
> remaining acceptance. Close worktrees only after all source is integrated and
> private configuration is preserved. Do not reset, discard, force-remove, stage
> a worktree as a gitlink, or treat source integration as permission for live
> migration/deployment/provider/device actions. Keep the operational gates above
> open until actually verified.

If any other agent is still active, coordinate exclusive Git mutations using
`.run/dev-recovery/coordination/git.lock` and full Core verification using
`core-checks.lock`, held as FileShare.None streams. Never nest, steal or delete a
held lock. Closing these chats does not stop the local services.

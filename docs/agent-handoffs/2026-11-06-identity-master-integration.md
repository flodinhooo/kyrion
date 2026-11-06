# Identity master integration after chats A/B

Date: 2026-11-06. Source integration and isolated acceptance only.

Latest follow-up: the owner authorized deletion of redundant full archives.
Checkout/build/dependency copies were removed after separately retaining and
SHA-256-verifying all 530 historical runtime files and private configurations.
Branches/commits and complete Git bundles remain. A read-only personal database
check found **V39**, with V40–V46 still pending. Core/Ollama/STT/TTS were reachable;
Web/Website/AI did not return successful probe responses. No live migration or
restart was performed. See the latest unified Identity handover section; older
full-archive retention statements below describe previous checkpoints.

Follow-up: both Identity worktrees have since been retired at the owner's
request. Their full directories and Git metadata were preserved under ignored
`.run/stabilization/identity-worktree-archives/2026-11-06-closeout/`; only their
old registrations were pruned. Both branches remain ancestors of master. The
preservation/retention paragraphs below record the earlier integration checkpoint;
see the updated unified Identity handover for the retirement procedure.

## Complete source integration and preservation

The owner authorized integration into primary `master` using the existing
worktrees. The primary started clean at `b0932ab`; both worktrees had no dirty
tracked or untracked source. Their ignored files were inventoried separately.

- `3ea5179`: complete merge of `integration/unified-identity` (`dcc2dee`), with
  Calendar usability/confirmed-copy work and schema-only tooling from current
  master retained. Git resolved the delivery-test tmpfs addition cleanly.
- `4df369c`: original `feat/unified-identity` (`fe25b0d`) ancestry retained. Its
  implementation was already cherry-picked and corrected in integration; this
  ancestry-only merge deliberately does not restore obsolete Identity V44.
- Both branch tips are verified ancestors of master. All their commits remain
  reachable; the full source is integrated, not a subset of the worktree.
- `73ee902`: final isolated build/test configuration, explicit cold-start setup
  acceptance and migration-plan target-version regression. The final handover
  commit is discoverable from this document's history.
- Subsequent corrections and this report are discoverable with `git log --`
  on the listed files. No primary branch switch, reset, stash or forced removal.

A complete verified Git bundle exists locally at ignored
`.run/final-integration/identity-source-history.bundle`. Private configuration
copies plus SHA-256 manifest are under ignored
`.run/stabilization/identity-worktree-preservation/`. The original worktrees,
branch refs, private configuration, ignored evidence and build caches remain
intact. They are retained as additional recovery copies, not pending source
integration. No secrets, node_modules, private voice files or build artifacts
were committed. Closing them is unnecessary for source completion and should
follow a separate owner-reviewed private-artifact retention decision.

## Reconciled integration boundaries

Master's V1–V45 SQL blobs are byte-identical to `b0932ab`; the active sequence is
exactly V1–V46. Identity V46 and its historical negative-test fixture are unchanged.
Old feature-only V44 history still fails normal validation without mutation.
No repair, out-of-order migration or live database migration was performed.

Calendar presentation keeps ADR0039; artifact-bound tooling keeps ADR0040.
Identity's decisions are now ADR0041 and ADR0042, with source references updated.
This resolves duplicate document numbers without renumbering applied SQL.

The schema-only operator tool previously rejected the combined JAR because it
required precisely V1–V45. It now accepts exactly V1–V45 or V1–V46 catalogs and
adds `--target-version 46`, retaining default45. Plans bind this choice along
with artifact/tool/catalog hashes, target identity and unchanged database state.
Future/gapped catalogs remain rejected. The existing advisory lock namespace,
read-only planning, source-drift, quiescence and protected-target checks remain.
Older plans must be recreated/reviewed with the changed tool, never reused blindly.

Website accepts `KYRION_BUILD_DIRECTORY` for independent build output, with
matching generated-directory Git/ESLint exclusions. Full acceptance uses separate
Website/Web dev output, refuses unrelated existing servers and leaves personal
runtime configuration intact. The cold-start setup test explicitly checks form
validity and HTTP201 before allowing 30 seconds for route compilation/navigation;
it does not bypass protected setup or manufacture a session. Automatic Playwright
failure DOM snapshots are disabled in this sensitive opt-in fixture because they
can contain input values; trace, screenshots and video remain off.

Identity links do not rewrite local user/role/Space/credential data. Existing
account/Space isolation, calendar participant editing/creator deletion,
connection-owner disclosure and destination consent, confirmed-copy presentation,
Gateway actor authority and append-only audit remain Core-owned and covered by
the combined suite. No cloud role or membership inference is introduced.

## Actual verification

| Check                                   | Result                                                                                                                                                                                                                                          |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Complete Core suite and bootJar         | 448 recorded, zero failures/errors, one explicitly opt-in standalone provider smoke skipped                                                                                                                                                     |
| Combined canonical migration tests      | Fresh V1–V46, representative staged upgrade preserving sixteen existing tables/checksums, repeat startup no-op, divergent Identity V44 rejection                                                                                                |
| Schema-only synthetic restore rehearsal | V39/V41/V43/V44 independently dumped/restored and upgraded through V46; rollback copies, stale-plan/target/history rejection; V45 destination/disclosure/delivery states preserved on restore and V46 upgrade; explicit V45 compatibility no-op |
| Web                                     | 262 tests in 68 files, lint, Next route type generation/TypeScript and isolated production build passed                                                                                                                                         |
| Website                                 | 40 regular browser tests, lint, typecheck and isolated production build passed                                                                                                                                                                  |
| Full real-service Identity browser      | One comprehensive scenario passed, 2.2 minutes including startup; actual Keycloak/Mailpit/three PostgreSQL stores and actual Website/Web/packaged Core, no intercepted routes/provider mocks                                                    |
| Offline tooling                         | 13 schema-tool tests plus six Gateway rollout-gate tests passed                                                                                                                                                                                 |
| Formatting                              | Targeted Website Prettier and changed Python Ruff lint/format checked; repository-wide historical formatting backlog unchanged                                                                                                                  |

The full browser scenario creates a central account, consumes the actual local
verification email, logs out/in on the website, establishes the local OWNER through
protected setup, uses existing local invitation signup for a non-OWNER, rejects
unlinked central login without user/role creation, links after local password and
device confirmation, logs in centrally as the original member with identical
permissions, observes real provider-token/session expiry, stops only fixture
Keycloak, verifies understandable outage and offline password login, unlinks with
password/confirmation, preserves the original member and OWNER grants, and logs
out. Outbound RFC8628 works without a public incoming local port or callback.
The standalone JVM smoke's skip is not reported as execution; actual packaged
Core/provider transport is exercised in the complete browser scenario.

The first cold browser attempt failed its five-second setup-navigation assertion;
the stronger explicit form/HTTP check and complete rerun passed. Dependency
relinking and overlapping build-lock attempts were excluded from acceptance;
final Web and Website checks ran after dependency completion and sequentially
within each app. Initial Ruff formatting findings were corrected. No failed run
is counted as a pass.

Durable local evidence includes the full-suite manifest and immutable reviewed JAR
under `.run/dev-recovery/schema-acceptance/da46cf93a2c647b4b903da6b1849ab35/`,
full XML copied to `.run/final-integration/core-full-master/`, final app logs in
`.run/final-integration/`, and the successful browser `.last-run.json`. All five
owned acceptance containers were stopped after the passing browser run; their
tmpfs synthetic databases were intentionally discarded. Personal Core PID12808,
the personal database and other services were not manually restarted or migrated.

After final Python formatting, the actual schema/Gateway rehearsal was repeated
successfully: **34 tests, zero failures/errors/skips**, build successful, unchanged
source hashes, manifest under
`.run/dev-recovery/schema-acceptance/20cd0fad6fb14690a588a081837b62a4/`.
This retests the final tool bytes rather than treating the earlier tool hash as
approval of a changed tool. The full-suite reviewed JAR SHA-256 is
`f73b47d1c55cc717804a77c88f07d23cf3ab807dc7714b03fb5e9f543b865130`;
its Windows/JDK synthetic acceptance does not establish ARM64 release provenance.

## Remaining work and operational gates

1. Follow the A/B closeout's original-data backup/independent restore, original
   credential/audit keys, writer fence, target identity and exact artifact review
   before any live schema rollout. Older V45 evidence approves only its artifact.
   ARM64/Pi provenance, Gateway destinations, legacy-button resave and controlled
   real calendar/hardware acceptance remain separate. No operational activation
   or productive provider/device write occurred here.
2. Deploy/configure a reviewed central provider, DNS, TLS, SMTP and registration/
   lifecycle policy separately. Loopback HTTP and local Mailpit certify none of
   these productive prerequisites. Local password use remains independent.
3. Implement the next invitation slice from
   [the concrete existing-invitation extension contract](../space-invitation-cloud-plan.md):
   provider-owned cross-client account UUID, OWNER-approved installation keys,
   narrowly scoped outbound broker, durable local outbox/inbox and idempotent
   local invitation redemption. No second invitation authority, general remote
   access or user-data synchronization is implemented. New remote recipients
   still need local password enrollment; offline acceptance stays pending.
4. Any actually installed divergent Identity V44 needs its own protected backup
   and reviewed compatibility plan; do not repair it into canonical history.
5. The existing recovery-helper ACL diagnostic and all A/B deferred product work
   remain open. No installer changes were made by this integration.

Reproduction: [full isolated Identity acceptance](../../infrastructure/identity/FULL_ACCEPTANCE.md),
`infrastructure/dev/Test-CoreSchemaMigration.ps1 -JavaHome '<JDK21>' -FullCoreSuite`,
and the existing V45 rollout/runbooks. These are verification instructions, not
authorization to point the tools at the personal installation.

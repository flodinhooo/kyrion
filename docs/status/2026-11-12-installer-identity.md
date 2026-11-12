# Installer continuation: linked account and Space onboarding

The complete original installer task remains open. This records executable work
and developer evidence, not a partial user handoff. Keep the
[full requirements ledger](../installer-requirements.md) authoritative.

## Implemented

ADR0053 extends the existing Core identity service, local authentication and
Space invitation authority, without a second account/Space database:

- First-owner RFC8628 setup is bound to the protected installer bootstrap secret.
  Provider proof precedes local creation. One transaction creates the existing
  local account/password hash, HOME/BUSINESS Space, roles, session, central link
  and audit. Failed setup consumes its proof and rolls everything back.
- Invited registration binds a separate operation purpose to the invitation
  hash. Existing expiry, use limits, delegated roles and Business mailbox/domain
  rules remain authoritative. Duplicate identity linkage rolls back account
  creation and invitation use; no OWNER role is inferred from a web account.
- The downloaded installer opens the provider browser or shows its verification
  URI/code, polls and continues locally. It collects a separate local offline
  credential for that same identity, never a website password. No operation
  token, application session or password is stored in installer progress.
- Existing linked identities log in centrally or with local offline credentials.
  Only Core's current active authorized Space is shown and explicitly confirmed.
  Non-administrative members stop before host/integration administration.
- `--continue-setup --target <owned-installation>` reopens the existing local flow
  without reloading a release bundle. Host ownership and Core authentication
  remain required. Provider settings are validated public configuration, shown
  before installation, journalled and passed to Core on Windows and Linux.
- Release profile assembly now derives the schema from the actual Core JAR's
  migrations. An explicit wrong schema is refused before output/vendor mutation;
  the hosted service workflow no longer hardcodes schema 48 against newer Core.

Core's one-active-Space guard remains enforced. This supports a new Space and
existing membership/invitation on the connected Core. A Space on another machine
requires the still-open prepared-agent enrollment work in R23-R29/R35. The website
directory is not authorization, device pairing or remote connectivity.

The historical “installer is unchanged” paragraph in unified-identity.md is
superseded for normal downloaded-installer onboarding by ADR0053. Existing local
Core users retain their credentials, permissions and independent local login;
central identity remains optional outside this new regular installer path.

## Actual evidence

- Core main/test sources compile and `bootJar` builds with private Temurin JDK
  21.0.13+9. Its official archive checksum was checked; no global JDK changed.
- Eleven existing OIDC provider/transport tests pass. They use actual HTTP/RSA
  verification against synthetic authorities, not production Keycloak.
- The full Python suite passed 148 tests on Windows (one platform skip); later
  schema-builder tests passed independently. Updated Linux/full totals are
  recorded below when complete.
- `tests/integration/verify-native-windows.py --linked-account --core-jar <built
  Core JAR>` runs actual PostgreSQL, Core, Web and Caddy with a new synthetic
  database and random loopback ports. Its local OIDC authority uses real TLS,
  an isolated Java trust store and RSA-signed identities. This is deliberately
  labelled a synthetic provider, never a production-account test.
- The live run passed new linked BUSINESS owner/Space, existing linked login,
  pending/cancelled/expired proof, failed-setup rollback and consumed-proof
  rejection, unknown identity denial, invitation membership in the same Space,
  delegated USER role, denied Space administration, duplicate identity rollback
  including invitation use, and spent invitation rejection.
- After stopping the provider, actual Core/PostgreSQL restart still admits local
  password login as the same linked user with the same BUSINESS membership.
  Web/Core internal TLS and the Web child-process ownership checks also pass.
  Report: `build/installer-linked-native-report.json` (allowlisted flags only).
- The Testcontainers identity/Space suites compile but were not executed locally
  because Docker is not running. The direct native SQL/HTTP scenario is separate
  evidence; do not present mocks or compiled tests as executed DB suites.

Source runs reuse authenticated public vendor binaries from the existing test
bundle, and explicitly override its historical Core JAR with the new source
build. Reports identify this override. These are process tests, with no service
registration, cold boot or network-isolation claim. No real accounts, household
devices, productive installation or release publication were used.

## Continue autonomously

Explicit legacy-account LINK consent is implemented and passed the live fixture,
preserving the same user and membership. Continue rebuilding updated frozen
artifacts and keeping the ledger current, followed by device enrollment/task
handover, integration/hardware, Ollama/Velora, transactional installed updates,
portable restore and adaptive tutorial requirements. Do not ask for partial user
acceptance or describe the whole installer as complete.

Windows recovery now creates the host key through the installer's atomic
Administrators-owned file API, before invoking Core's `provision-prepared`
console command. Protected key intent precedes creation in the journal; failed
Core operations preserve it for retry. Installer maintenance also dispatches
existing Core open/complete/rotate operations on Windows and Linux, without
capturing passwords or codes. Prepared-file and orchestration tests are distinct
from elevated console/ACL and cold-boot acceptance, which remain unperformed.

The independent Linux AMD64 `.6` native archive was built inside the isolated
Debian guest and passed its frozen-program probe. Its local metadata records
source digests and `platformInstallationAccepted: false`; this is neither a
published download nor an installation/boot acceptance. Build-only dependencies
binutils and libpython3.13 were added only inside that guest.

### Windows peer verification follow-up

The developer host sometimes reports the exact reverse TCP tuple and expected
child PID with state 0 or LISTEN rather than ESTABLISHED, even after waiting.
Those snapshots are rejected. The TLS transport now closes the rejected socket
and makes at most four new connections, each subject to the same strict kernel
ownership proof and child-liveness checks before any decrypted bytes are sent.
Malformed table errors and child exit are not retried. Microsoft documents the
[row layout and established-state field](https://learn.microsoft.com/en-us/windows/win32/api/tcpmib/ns-tcpmib-mib_tcprow_owner_pid);
no unsupported state is treated as proof of an established peer.

The updated Windows suite passed 162 tests (one platform skip). Four policy
fixtures cover socket cleanup, bounded failure, child exit and malformed table
failure; these are mocks. A separate actual Windows SDK run proved 100 consecutive
connections to an isolated child process, sending no application bytes. The
actual TLS test also checks that a wrong expected PID receives no credentials.
This does not establish cold-boot or elevated service acceptance.

The subsequent recovery-maintenance source passes 169 installer tests on
Windows (one skip) and in the isolated Debian guest (16 platform skips).
Whole-installer Ruff passes; the changed PowerShell helper parses successfully.
Core's protected-security-file JVM test and bootJar build pass with the private
JDK 21 toolchain. Recovery journal, dispatch and cancellation cases use mocks;
they do not prove real elevated service/interactive-console behavior.

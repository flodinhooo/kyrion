# Existing Core enrollment acknowledgement and schema 50

This continues the full installer scope, not a completed multi-device installer.
The [binding ledger](../installer-requirements.md) still marks node roles,
installer enrollment, agent lifecycle and distributed coordination as source work.

## Implemented

[ADR 0081](../adr/0081-retryable-existing-node-enrollment.md) extends the existing
Core gateway identity and enrollment instead of introducing another system.
Prepared clients may supply their protected canonical 256-bit URL-safe node
credential. Core stores its existing hash only. A committed registration is
associated uniquely with the consumed code and constrained to the same Space.
Inside the original expiry, the exact same credential and identity fields can
acknowledge the same node after a lost response. Other credentials, changed
metadata, expired codes and legacy replay fail. Concurrent same-client retries
return one node; competing claimants cannot both register. No duplicate account
or Space is created. Existing server-generated credential clients still work.

The existing agent controller advertises enrollment protocol 2 through a typed
capability response, allowing prepared clients to refuse old servers before
sending a one-use code. This endpoint does not enroll or authorize anything.

V50 adds a nullable enrollment association, unique index and composite Space
foreign key. Legacy rows are not guessed/backfilled. Existing Core restore/update
recovery clears the association while preserving owner/node identity and rotating
credentials. Standalone restore/backup-verification helpers declare schema 50;
the update helper explicitly accepts source49/source50. Installer fresh download
selects current schema50; portable restore accepts only reviewed schema49/50,
strictly validates helper capabilities, and still checks actual prepared schema
and the trusted binary descriptor before importing. Unknown schemas remain
unsupported by that portable-restore contract.

The existing artifact-bound schema operator tool now accepts contiguous catalogs
through V50 and explicit target50. Future catalogs still fail. Default target45,
quiescence, immutable artifact/plan hashes and no-downgrade rules are retained.
No live schema tool, deployment or release publication was performed.

## Verification

- **210 Core tests pass, one skip, zero errors/failures** in the complete security
  and gateway run. This includes actual PostgreSQL migration, HTTP retries,
  concurrent equal/different claimants, cross-Space FK refusal, cleanup and
  schema-only rehearsals. The preceding run had eight failed rehearsals because
  the tool's reviewed catalog ceiling was V49; that failure is retained and the
  full corrected run passes. **16 operator-tool rejection/catalog tests pass.**
- **483 Windows installer tests (nine skips)** and **491 isolated Linux tests
  (twenty skips)** pass. Fresh-download fixtures are explicitly schema50; update
  fixtures retain their explicit legacy schema49. New strict capability tests
  reject booleans, floats, missing authority and future schemas.
- Actual Core/PostgreSQL/GnuPG process tests pass full encrypted capture,
  inactive verification database, interrupted binary import, source retirement,
  target activation, role/link/knowledge preservation, credential revocation and
  offline login. Bound enrollment data is included and cleared by real Core
  restore disposition. Linux uses an isolated namespace; Windows verifies the
  actual runtime files but injects service/privileged ACL boundaries. These are
  not SCM, Docker or physical-boot acceptance.
- The current schema50 process update passes both successful interrupted
  activation/recovery and a failing nontransactional migration with interrupted
  database rename. Its target51 migration is a synthetic test sentinel, not a
  released or generally supported schema51. Actual recovery returns schema50
  without attempting a downgrade, preserving identities and revoking old grants.
- Immutable Core JAR SHA-256:
  `92dfd2bc8c9a8bd59a12f66ae35dbd93930d1aefd331b49b29e7151b2b8fb2f8`.
  Evidence: `build/core-enrollment-security-final-report.json`,
  `build/isolated-linux/application-restore-schema50-report.json`,
  `update-transaction-schema50-report.json`, and
  `build/native-verification-process-1b532e0dd9ff49b6bfc32bb1ddaa3a78/report.json`.
- Native development `.20261114.25` passes executable/resource and exact
  source/artifact checks. Windows EXE: 12,772,237 bytes, SHA-256
  `9369bd0ae1119f40afda9b39c2cee962d7b41835a4f38d657cc87e432d38b24a`.
  Linux AMD64 archive: 14,581,032 bytes, SHA-256
  `f940d39057c1638420ba830bce91554d5d9c058cf84e85fbf88289c264e4dd36`.
  These installer packages do not bundle that Core JAR; a reviewed signed runtime
  release is separate. They remain unsigned, unpublished and
  `platformInstallationAccepted: false`.

Prepared agent credential persistence, restricted verified-TLS transport and
installer wiring are ongoing work, not claimed complete by this Core checkpoint.
No public website wizard or public agent endpoint was introduced. Do not ask the
user to accept this intermediate state; continue the open implementation.

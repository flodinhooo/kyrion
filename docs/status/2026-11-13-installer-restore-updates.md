# Installer continuation: operational restore and updates

The overall installer assignment remains open. This report supersedes the
restore work order in the preceding integration report; it is not a request for
user acceptance.

## Implemented restore path

ADR 0057 defines the source-fenced, fresh-target restore protocol. The existing
installer now captures a PostgreSQL 17 binary table snapshot alongside the
encrypted operational backup. It prepares a signed, compatible fresh runtime
without activating it. An explicitly retired source emits an authenticated
receipt bound to the backup digest and the new installation UUID. The target
verifies that receipt before importing data into the schema created by its own
verified Core. Archived SQL, functions and schema definitions are not executed.

Original accounts, memberships, Spaces, encrypted application keys and knowledge
are preserved. Core owns the transactional security disposition: old sessions,
recovery grants and device credentials are invalidated; pending device commands
are failed; integration control and scheduled calendar synchronization require
review. Core verifies the existing audit chain and appends a sealed restore
event in the same transaction. The target receives a new host identity.

Import interruption is resumable while the target remains inactive. Repeating a
completed restore does not replace subsequently written application data.
Managed-key replacement has explicit crash recovery checkpoints.

## Developer evidence

- Windows source suite: 227 tests, one skip.
- Isolated Debian Linux source suite: 227 tests, 16 platform-specific skips.
- Core permit/security unit tests: four tests passed with JDK 21.
- Real PostgreSQL 17 binary snapshot roundtrip on Windows, including every byte
  value, quoted paths, sequence restoration, repeated import and invalid foreign
  keys. This is a native process test, not SCM acceptance.
- Real Core/PostgreSQL/GPG application restore on both Windows and isolated
  Linux: source retirement, inactive preparation, interrupted import, corrupted
  audit rejection, audit-write transaction rollback, offline login after process
  restart, preserved Space/account/link rows and new host identity passed.
  Lifecycle operations use a process adapter, not Docker/SCM. Linux uses a
  private network namespace with no egress. The identity link is a seeded test
  fixture; this does not replace browser SSO acceptance.
- Tested Core JAR SHA-256:
  `2234b42a07a271d474ddfd3c2ea853f1780c9f7d1d0d40f6bed30e7fdeddd056`.
- Ignored local reports: `build/application-restore-windows-report.json`,
  `build/isolated-linux/application-restore-report.json`,
  `build/portable-database-windows-report.json`.
- CI prepares the corresponding PostgreSQL 17 Linux scenario and the native
  Windows service restore scenario. These workflow changes have not been run
  on hosted runners in this development session.

No real household devices, public releases or host services were changed.

## Explicit boundaries and remaining source work

Portable activation currently requires PostgreSQL 17, schema 49, an exactly
matching trusted target schema and a new or matching prepared target. Legacy
dump-only backups can still be verified, but are not activated by this path.
An unavailable or unfenced source cannot authorize activation. Same-root
disaster recovery, arbitrary schema transitions and distributed authority
transfer remain implementation work. Native Windows SCM restore, actual
container UID permissions and cold boot remain target-environment acceptance.

Automatic installed update checks and transactional updates are the next work
item. Signed compatible candidate selection already exists; it is not automatic
installation. Old `.2` native installer artifacts predate this restore code and
must not be presented as containing it. The complete installer requirements
matrix remains authoritative for all other open work.

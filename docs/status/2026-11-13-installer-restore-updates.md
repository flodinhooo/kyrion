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

## Installed update checks (ADR 0058)

The native installer now offers `--updates configure|status|disable|rotate-trust`. Explicit
configuration reviews the HTTPS feed, independently supplied public trust store
and executable digest before copying an immutable maintenance worker. A Windows
SYSTEM boot task repeats daily; Linux uses a root oneshot service with a boot
and daily timer. No interactive login or user Python is required. The background
entrypoint runs without prompts. It reuses the real signed release checker and
persists a policy-bound attempt/result. Failures preserve the last verified
result and store only an allowlisted error code. Retirement and uninstall remove
only the owned schedule. Timer publication is atomic and registration resumable.
Installed trust rotation reuses the signed rotation verifier, advances exactly
one epoch and changes the policy revision without changing the OS task. Replay
and a changed reviewed rotation document are rejected.

Actual Windows COM definition validation and actual isolated Linux
`systemd-analyze verify` passed, without registering or starting host jobs. Unit
tests cover real signature selection, network failure, stale policy revisions,
inactive targets, invalid URLs, interrupted publication and configuration resume;
SQL, frozen-worker and scheduler boundaries are injected in these unit tests.
The Windows hosted integration runner additionally prepares real SYSTEM task
execution of its unreleased worker and verifies rejection before network access.
That privileged scenario has not been executed in this session. Local Debian
has no running systemd manager; no Linux job execution or cold boot is claimed.

Configuration currently requires a released embedded version and an explicit
authenticated feed. Development builds cannot pretend that a public release
exists. The `.4` native Windows/Linux test packages contain the current
allowlisted sources, verified against both embedded source hash maps. They
remain unsigned, unpublished development artifacts. Local Web update
notifications, transactional installation, maintenance windows, migrations,
interrupted update recovery and distributed coordination remain source work.
Checking does not install an update. The complete requirements matrix remains
authoritative for all other open work.

Current source suites: 238 tests on Windows (one skip) and isolated Debian Linux
(16 platform skips). Ruff passed, DE/EN locale keys match, and both prepared CI
workflow documents parse. No hosted workflow was dispatched.

| Local artifact | Bytes | SHA-256 | Verification |
| --- | ---: | --- | --- |
| `build/native-installer/kyrion-installer-0.0.0-dev.20261113.4-windows-amd64.exe` | 12417292 | `2a1a31964bffb30967e71a77b0fc80bb9abf2b1d7c4ca22017d3dca1d87d7bc7` | Actual frozen version/probe, current source map; no service/cold boot acceptance |
| `build/native-installer/kyrion-installer-0.0.0-dev.20261113.4-linux-amd64.tar.gz` | 14222644 | `6ed5bcc0c7c4cfc1a9869a7b38361e6694342ee6b8cf3c54906d2f86471b5901` | Actual frozen version/probe on isolated Debian; no ARM/old-glibc/boot acceptance |

These ignored build outputs are not public download links or published releases.

The updated local Windows runtime bundle is
`build/windows-native-bundle-dev8/kyrion-windows-amd64.zip`: 247559859 bytes,
SHA-256 `705afe1d15c07b5c273f7c557270ce721f9c59b3eaa9d0870266bc61951272e2`,
6114 public files. Its manifest digest is
`61ad722570fcfa139939849991acea5bea279e86b27fcca9e8611f577ed8cc38`.
The actual frozen `.4` installer accepted its ephemeral development signature
and verified the full payload without activation. The private test signing key
was never persisted. This is not Authenticode or productive release acceptance.

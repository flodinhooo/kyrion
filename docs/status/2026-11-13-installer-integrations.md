# Installer continuation: Home Assistant and isolated Linux evidence

The overall installer scope remains open. This is developer evidence and a
continuation record, not a request for user acceptance. See the complete
[requirements ledger](../installer-requirements.md).

## Executable changes

- The downloaded installer imports an explicitly confirmed Home Assistant area
  through Core's existing room API. Existing unambiguous names are reused;
  concurrent exact-name conflicts are re-read once. Invalid or ambiguous names
  fail without creating another room. The default type is `other`; users can
  change it in the existing local room UI. Room creation needs Core's room
  permission separately from integration configuration.
- The wizard shows the actual imported catalog immediately, including rooms,
  availability, supported capabilities and observed state. Only an explicit
  TEST/device/TURN-ON or TURN-OFF sequence calls Core's device-command endpoint.
- `--home-assistant configure|status|disconnect` returns to integration
  management independently of optional hardware/AI setup. It reuses normal
  linked-account/offline authentication, authorized Space selection and Core
  permissions. Disconnect requires explicit consent and a subsequent Core
  configuration check. It does not unpair physical devices or modify HA itself.

## Verification and limits

179 installer tests passed on Windows, with one platform skip; whole-installer
Ruff passes. Six room cases and four maintenance cases are HTTP/orchestration
mocks and are identified as such. Existing actual Windows TCP/TLS acceptance
remains separate from elevated service and cold-boot acceptance.

`tests/integration/verify-linux-core.py` additionally ran actual PostgreSQL 17
and the source Core JAR under Debian 13 AMD64 in the private WSL developer guest.
The test process is unprivileged. A dedicated network namespace has only the
loopback interface and synthetic private address 10.231.0.1, with no external
interface. It refuses another topology. JRE/PostgreSQL are test-only guest
packages; no production or host services are installed. The observed schema is
49; the report includes the actual source JAR digest.

The run uses real Core TLS, SQL/migrations, a synthetic HTTPS/RSA OIDC authority
and a synthetic HA-compatible HTTP provider. Production installer onboarding
functions receive deterministic terminal answers through a test-only direct TLS
adapter; API replies and transactions are real, not mocked. It verifies linked
BUSINESS owner/Space, selected light without its unselected sensor, confirmed
room import, exactly one deliberate synthetic action, background state refresh,
removed-entity control withdrawal, token/selection disconnect, and the same
offline identity/Space after provider shutdown and Core/PostgreSQL process
restart. No real account, provider credentials or household device is used.

The background-refresh assertion reads SQL directly before requesting the
catalog, so on-demand refresh cannot satisfy it. A 30-second scan combined with
the existing 30-second per-owner throttle may defer refresh to the next scan;
the fixture allows 75 seconds. This is polling, not realtime event delivery.

Local evidence: `build/isolated-linux/core-ha-report.json` and private developer
run logs. The manually triggered `installer-linux-core.yml` workflow prepares
the equivalent namespace scenario on an Ubuntu 24.04 disposable runner with
PostgreSQL 16 and explicit JDK 21. Its YAML has been parsed locally; that hosted
workflow has not been dispatched or claimed successful.

These are component/process acceptance tests. They do not prove a complete
Linux service installation, systemd boot, Windows elevation, USB/audio/GPU
support, actual Home Assistant compatibility across versions, distributed
device enrollment, full encrypted application restore or installed updates.
Continue those source requirements and available tests autonomously; no partial
user test is needed.

## Embedded installer version follow-up

The frozen installer now contains an explicit build identity and implements
`--version`. Missing/malformed/duplicate build data is rejected in a frozen
program. Source/Python-archive runs identify as `0.0.0-dev.0`, never as a released
`1.0.0`. The CLI cannot override its own version for compatibility checks.
Development builds refuse stable update-feed selection before network access.
This does not implement the still-open installed update transaction/service.

Both native builders execute the actual frozen `--version` and compare it with
the requested version. Service-host builds accept the same explicit `--version`;
profile assembly checks their build metadata and packaged identity match the
profile version before copying vendors. The website publication-catalog tool
also requires embedded-version verification in addition to its existing release
asset/platform-acceptance checks. No download is activated or published.

The Windows standalone `0.0.0-dev.20261113.1` executable and matching one-directory
service host were built and smoke-tested locally; their metadata retains false
installation/boot acceptance. Latest source verification passes 185 Windows
installer tests (one skip), whole-installer Ruff and parsed workflow YAML.
The same version source passes 185 tests in Debian (16 platform skips), and its
standalone Linux archive passed both the frozen inventory probe and exact
embedded-version check. These are development downloads in `build/native-installer`:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `kyrion-installer-0.0.0-dev.20261113.1-windows-amd64.exe` | 12346411 | `eecb419aa1675ed92527fbb0ead88bb324553469588cf01212bc8ea48160ce0b` |
| `kyrion-installer-0.0.0-dev.20261113.1-linux-amd64.tar.gz` | 14148769 | `7d8f3afd24d8319be21947813a76c93426a361f9ea0ce3fd0956b0da0d620961` |

Each artifact's adjacent metadata records its actual sealed input hashes. They
are unsigned, unpublished, and do not claim platform installation acceptance.
The Linux executable was built/probed on Debian 13 AMD64; this does not prove
older glibc distributions, ARM64/Pi, Docker provisioning or system boot.

## Software-removal regression and SCM deletion ordering

Source reinspection corrected an overly broad missing-payload exception added
during this continuation. Actual provisioning stores public payload digests in
the separate signed native manifest, not the configuration-file journal. The
earlier fixture incorrectly used `Installation.write` for those payload files.
The exception has been removed; ordinary journal integrity remains unchanged.
The corrected fixture uses the actual separate-manifest layout and confirms
that software-only removal can already resume partial payload deletion without
weakening key/configuration checks. Service removal now closes each SCM handle
and waits for actual deletion before program-file cleanup.

Five tests use real private temporary files plus mocked SCM/elevation. They prove
interruption/reload/repeat, data preservation, rejection of changed or missing
retained keys before service access, and handle-close/wait ordering. They do not establish
real elevated uninstall acceptance. Fully resumable deletion of the complete
installation including its final journal is still source work; the software-only
regression coverage and SCM fix do not close that requirement.
The complete updated Windows source suite passes 190 tests (one platform skip)
and whole-installer Ruff; the five cleanup tests also pass independently in the
normal developer context. The restricted sandbox cannot apply test-file owner/
group descriptors, so this is distinct from a sandbox-only run.
The updated Debian source suite also passes 190 tests with 16 platform skips.

## Complete bundled Windows process acceptance

The clean Web build was prepared from tracked public `apps/web` sources in a
new build directory, with offline locked dependencies, a minimal build
environment and no copied `.env` files. Its source-hash receipt is
`build/windows-web-native-dev7-source.json`. The actual source Core JAR, parser,
this Web build, the versioned service host and pinned public vendor binaries
were assembled into `build/windows-native-bundle-dev7`. Schema 49 was derived
from the actual JAR rather than supplied manually.

The test-only signer retained no private key. The frozen standalone installer
accepted the signed manifest and verified the payload without activating it.
Bundle ZIP SHA-256 is
`bee083ecfe1858121f32ee234d298e0af728d77f75621344c86dfa79b0377927`;
manifest SHA-256 is
`5b08e7ce38bd9d5a8697346e1b38488826d68687e569f31c4f4fbda5911af993`.

`verify-native-windows.py --linked-account` then ran the **bundled** Core and
Web, with fresh native PostgreSQL and a synthetic HTTPS/RSA provider. Unlike
the historical dev5 run, `sourceCoreOverride` is false. The source Core digest
is `c6dc816f731b7c84e83b0a238a1e7428b80a0062ae740c6311f6d7a0fb40d425`.
All report assertions passed: linked first owner, BUSINESS Space, invited USER
membership and denied administration, legacy identity linking in place,
cancelled/expired/reused proof rejection, transactional rollback including
invitation use, setup without optional equipment, unchanged linked identity
after provider shutdown/process restart, closed bootstrap, pinned Core/Web TLS
and verified Web-child ownership. Report:
`build/installer-linked-native-dev7-report.json`.

This starts only disposable user processes and synthetic data. It registers no
services/tasks, changes no global trust store and claims neither network
isolation nor elevated Windows/host-boot acceptance. Development bundles and
downloads remain unpublished and are not ready for overall user acceptance.

## Portable operational-backup dependency and archive validation

ADR0056 retains the existing GnuPG operational-backup format. The pinned
Windows vendor executable and corresponding source archive are both verified
against the official release primary key. The build extracts public AMD64
runtime files as data without running the NSIS installer, retains corresponding
source, detached signature, public release keys and original component COPYING
notices, and creates an empty portable marker. Profile assembly verifies the
exact public file receipt before copying into the signed installer namespace.
The manually triggered Windows service workflow now builds and exercises this
profile; that workflow has not been dispatched.

The actual prepared development profile `build/windows-gpg-profile-dev2`
contains 102 hashed files. Its native GnuPG 2.5.24 passes synthetic encryption,
decryption, wrong-password rejection and legacy interoperability in both
directions; payload hashes and directories remain unchanged. Evidence:
`build/windows-gpg-source/portable-runtime-dev2-report.json`. No vendor system
installer, service registration or production data is involved. The helper uses
absolute GnuPG and matching gpgconf paths and checks temporary-agent cleanup.
Archive inspection additionally rejects duplicate JSON keys, ambiguous numeric
types and malformed file records before any restore extraction.

The complete Windows source suite passed 196 tests (one platform skip) before
the additional strict-manifest regression; that regression passes in the focused
14-case recovery suite. The updated isolated Debian 13 suite passes 197 tests
with 16 platform skips (`build/isolated-linux/test-report-current.txt`).
Ruff lint passes across the installer. Whole-tree format
check identifies nine pre-existing files; changed GnuPG producer/profile/tests
pass formatting. Native capture, full application restore, identity fencing and
backup scheduling are still missing source work. This dependency does not close
R70/R72 or imply overall installer acceptance.

Windows payload ACL provisioning now explicitly sets protected BA ownership and
service read access on every payload object and verifies it before starting
services. PowerShell parsing and source tests pass; actual elevated ACL/SCM and
cold-boot acceptance remain unperformed. No host services were registered.

## Native capture implementation continuation

`native_backup.py`, called by Windows `--backup`, now validates owned private
installation state and manifest-hashed PostgreSQL/GnuPG files before execution.
It validates all service identities before stopping anything, refuses transitional
or inconsistent dependency states, keeps PostgreSQL running for a logical custom
dump and pauses only initially running Core/Web/Caddy services. A durable journal
records restart obligations before the first stop; an interrupted operation is
reconciled on its next backup invocation. Failures attempt every required restart
and retain an unresolved obligation rather than reporting success.

The archive includes original keys, native/identity configuration, certificates,
knowledge and available host recovery files. It excludes public runtime payloads
and live database files. Plaintext dump/archive files are created with the
protected journal's owner/DACL before writing. Services resume before encryption;
publication uses a no-overwrite link. Restore remains explicitly unverified.

Eight injected-SCM tests prove ordering, timeout/error recovery, interrupted
journal reconciliation and real archive coverage with synthetic SQL/tool outputs.
The actual GnuPG runtime test remains separate. The elevated Windows service
acceptance runner now also performs capture/decrypt/inspection on its disposable
installation; it has not been run here. The full Windows and isolated Debian
source suites each passed 203 tests before two additional journal regressions;
those regressions and the updated package test pass separately. The final
Windows source suite passes 205 tests (one platform skip). No actual native
service capture, full application restore or host reboot is claimed. Backup
scheduling and full restore/identity disposition remain source work.


A new standalone Windows development artifact includes this capture module:
`build/native-installer/kyrion-installer-0.0.0-dev.20261113.2-windows-amd64.exe`,
12,355,544 bytes, SHA-256
`0293fe21f0b23b427070ed83a44000e77658becd44281e0c8d59ae2c2db3b617`.
The builder records sealed source hashes and verifies embedded version and
actual frozen probe execution. It is unsigned/unpublished and is not platform
installation acceptance. The portable GnuPG profile remains a separately
assembled runtime-bundle dependency, not embedded in the standalone bootstrap.


The matching isolated Debian 13 source run also passes 205 tests (16 platform
skips). Linux AMD64 native development artifact `.2` is 14,161,461 bytes with
SHA-256 `b3afeb60f58e30cf41341710f79f638a61777d34bec50ac8ff22e0a13290efe6`.
Its frozen version/probe checks pass in Debian 13; this does not cover older
libc distributions, ARM64/Pi or boot. Both `.2` artifacts precede the following
update-check continuation and must not be described as containing that change.

## Native signed update-check continuation

Windows `--check-updates` now reads the actual schema through manifest-verified
PostgreSQL tools and the existing protected local connection. It reuses the same
signed release-index/compatibility policy as Linux; it does not install updates.
Checks persist the verified index digest and trust epoch and refuse trust rollback
or different signed content at the same index sequence. Five real Ed25519 tests
with injected network/native SQL verify compatible selection, wrong signature,
schema mismatch, sequence rollback/equivocation and trust-epoch rollback. The
privileged service acceptance runner also compares its real native schema query
with the captured backup schema; that runner is prepared but unexecuted.
Installed scheduling, transactional update/migration/recovery and distributed
barriers remain source work. No production feed/key is fabricated.


Current update-check source verification: Windows 210 tests (one platform skip),
isolated Debian 13 210 tests (16 platform skips); whole-installer Ruff lint and
changed-file formatting pass. Later DE/EN maintenance/update guidance keys were
also checked for complete translations. These are source/injected integration
tests, not elevated native SQL/service or cold-boot acceptance. The requirement
matrix remains open and has been updated for native capture and signed checks.
The next maintenance work is full isolated application restore with explicit
identity disposition, then installed update scheduling and transactional update/
migration recovery. R23?R29/R35 distributed enrollment/Space selection and the
remaining integration/runtime/voice/tutorial/UI scope also remain source work;
none is delegated to user testing or silently removed.

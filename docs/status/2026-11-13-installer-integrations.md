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

## Software-removal interruption follow-up

Native Windows software-only removal now resumes after a partial payload
deletion. Only a protected journal already in `uninstalled` state can tolerate
missing payload files; remaining payload bytes, keys and non-payload metadata
retain strict integrity checks. Ordinary loading/writing/repair does not acquire
this exception. Repair after removal asks for a reviewed bundle before touching
services. Service removal closes each SCM handle and waits for actual deletion
before program-file cleanup.

Five tests use real private temporary files plus mocked SCM/elevation. They prove
interruption/reload/repeat, data preservation, rejection of changed payload or
missing retained keys, and handle-close/wait ordering. They do not establish
real elevated uninstall acceptance. Fully resumable deletion of the complete
installation including its final journal is still source work; the software-only
fix does not close that requirement.
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

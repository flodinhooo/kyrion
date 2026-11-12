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
Earlier integration source passes 179 tests in Debian (16 skips). An updated
Linux frozen build and source suite are being run separately; do not infer a
passing result from this continuation record.

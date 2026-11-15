# Owner-to-target pairing transfer checkpoint

The full installer assignment remains open. No user acceptance or publication is
requested. ADR 0087 defines the transfer and its trust boundary.

## Implemented

The local central installer now offers `PAIR` in `--devices`, including before any
devices exist. It uses the existing linked-account flow, Core session, current
Space and authorized gateway-enrollment API. A real pinned, local-only TLS probe
of the configured Caddy ingress precedes code issuance. No session credential is
forwarded through this public capability probe. A protected, exclusively created
local transfer file contains the ten-minute one-use code and public trust data;
captured output contains metadata only. There is no website wizard or upload.

The target installer accepts `--node-pairing` for foreground preparation or the
Linux system service. It validates a bounded strict JSON format, certificate
digest, UTC expiry and private file attributes, then reviews immutable in-memory
data before materializing temporary private files. Existing enrollment, journal,
technical UID, Core identity and task authority are reused. Same-input retry is
idempotent; imports cannot retarget an existing identity or grant tasks. Root can
import a private file belonging to the local user who supplied it; ordinary users
cannot import another user's file. Stored agent credentials remain service-owned.

Invalid URL credentials are rejected before review output can display them. Old
or missing ingress fails before enrollment issuance with an explicit upgrade
diagnostic; export does not silently replace existing proxy configuration.
Hostname/DNS reachability from the target remains unproven until its actual
connection. A transfer is a temporary bearer capability, not a signed public
release: private transfer and certificate-fingerprint comparison remain required.

## Actual developer evidence

- Windows installer suite: 522 reported tests, eleven platform skips. Linux:
  532 reported tests, twenty skips. Gateway: 61 passed/sixteen Windows skips;
  77 Linux passed. Ruff, changed-file formatting and workflow YAML parsing pass.
- The frozen Linux installer `0.0.0-dev.20261115.12` passed actual configured-host
  Caddy/verified-TLS/Core/PostgreSQL export and target import. Core rejected reuse
  of a consumed code and expiry controlled in the disposable database. One node
  and its existing identity were preserved, and no task was implicitly granted.
  The current Space was actually BUSINESS; its identifier matched node ownership.
- Only terminal choices and the owner process-fixture transport adapter were
  supplied. Core, gateway and proxy success responses were not mocked. No provider
  browser login or operating-system service is claimed by that network fixture.
- A separate actual PID-1 systemd fixture passed importing a Core-issued transfer
  into the dedicated non-root service: real heartbeat, restart, Core outage and
  reconnect, identical-input repeat, conflicting transfer refusal, disable,
  repair and service removal. This fixture assembles the transfer from the real
  Core enrollment response; the first fixture covers the central export path.
- Core JAR: `998ddd7a7e88d99a052ada709882fcf83f3e6022aec149749c45ad1853057f00`.
  Private reports are `build/isolated-linux/pairing-transfer-report.json` and
  `node-service-report.json`. Their installer-binary hashes match.

The manual Linux workflow includes both repeatable fixtures. Its pairing test
uses a private mount/network namespace, a configured test hostname and the
existing official Caddy test image resolved to a local immutable image ID. Only
summary reports are uploaded, never transfer files or credentials. Hosted
execution was prepared, not triggered. No household action, paid call or productive
installation occurred. Windows elevated export, Windows prepared nodes, ARM64
and physical cold boot are not accepted by these results.

| Private native artifact 0.0.0-dev.20261115.12 | Bytes | SHA-256 |
| --- | ---: | --- |
| Windows AMD64 | 12,872,406 | `f7119ea1b5fa393c414260d95b37e064c2b7b6f0bb4e1b656098f756893bb974` |
| Linux AMD64 | 14,675,561 | `fcb326a9189112320e3532c43131099c8c7174c3192e95a88b26723cf657210a` |

Both private native builds pass version/channel/public-CA smoke checks and match
all sealed checkpoint sources. The archive hash above differs from the extracted
Linux executable hash in process reports. Neither artifact is signed, published
or generally accepted for release. The Core JAR is a separate runtime artifact.

## Continuing scope

Existing-proxy extension with durable resume/recovery is next. Full task placement,
Windows prepared storage/service, exclusive cross-device handoff, node updates,
backups/data uninstall and local management UI remain implementation work. R23-R29
and the rest of the binding requirements ledger remain open as recorded there.

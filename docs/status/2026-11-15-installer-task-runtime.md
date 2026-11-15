# Prepared-node task runtime checkpoint

The complete installer assignment remains open. No user acceptance or public
release is requested. This supersedes the foreground-runtime limitation in the
previous embedded-node checkpoint, not the remaining service/deployment scope.

## Implemented behavior

The frozen installer embeds ten explicitly sealed existing gateway modules.
`--node-run` reviews and starts the existing prepared identity under an exclusive
local configuration lock. Core returns a device-authenticated, bounded task
permission lease. Unknown, expired and unreachable authority fails closed;
revocation stops the process. Reconnection uses bounded backoff, preserves the
identity and does not replay completed commands. Linux suspend-aware expiry
prevents standby from extending permissions. Hardware observations and local
integration events are scoped to granted tasks. No microphone is activated.

Reported runtime version 0.2.0 is separate from immutable enrollment metadata,
so a later heartbeat does not invalidate lost-response enrollment retries.
The version is source-only and unpublished. No installed device updates itself
merely because this repository changed. See ADR 0085.

## Developer verification

- Core security/gateway suites: 218 tests, zero failures/errors, one skip.
- Windows installer: 506 tests, nine platform skips. Windows agent: 54 passed,
  sixteen platform skips. Isolated Linux installer: 514 tests, twenty skips;
  Linux agent: seventy passed. Ruff and changed-file formatting passed.
- Actual frozen Linux executable, actual Core schema 51/PostgreSQL and verified
  TLS passed enrollment, immutable identity, heartbeat, duplicate-runtime refusal,
  Core process loss/reconnection and revoked-runtime exit.
- The same complete fixture also passed through actual Caddy with the restricted
  agent route allowlist and upstream TLS verification. Core JAR SHA-256:
  `998ddd7a7e88d99a052ada709882fcf83f3e6022aec149749c45ad1853057f00`.
- Core rejected commands for an unassigned node. After authorized assignment,
  actual queue/transport/completion worked without replay after reconnection.
  The final MQTT provider was an explicitly injected recording executable:
  **no physical-device control was tested or performed**.

Repeatable evidence: `tests/integration/verify-installer-node.py`, with actual
binary/JAR digests and optional `--caddy` plus `--caddy-sha256`. Network isolation
belongs to the caller. Private local reports are
`build/isolated-linux/frozen-node-report.json` and
`build/isolated-linux/frozen-node-proxy-report.json`. Captured output contains no
credentials. Terminal choices are supplied through a pseudo-terminal; Core
responses and the TLS proxy are not mocked.

| Private native artifact 0.0.0-dev.20261115.4 | Bytes | Archive SHA-256 |
| --- | ---: | --- |
| Windows AMD64 | 12,844,739 | `f4f8e113020f608232b1dd2f4d87ba2e7028d5b21c76e31d52a06797d2265191` |
| Linux AMD64 | 14,648,020 | `a6b0d7f79f2dfdd47c2cb2681c96347ca97d1b92754bdf582cc15cb934469126` |

Both builds match sealed checkpoint sources and passed native smoke/version
checks. Windows service-host compilation/smoke passed separately. Artifacts are
unsigned and unpublished; this is not Windows SCM, ARM64, physical cold-boot or
prepared-agent operating-system service acceptance.

## Remaining implementation

Dedicated prepared-node system services, owner-facing pairing export, reviewed
proxy extension for existing installations, Windows prepared storage, exclusive
cross-device task handoff, distributed AI and the complete local management UI
remain source work. A configuration lock is not a cross-device authority fence;
a permission lease is not exclusive ownership. R23-R29 and all other open ledger
requirements remain binding. The next implementation step is durable node-service
deployment with protected credentials and real operating-system verification.

# Existing-installation agent ingress checkpoint

The complete installer assignment remains open. ADR 0088 defines this maintenance
transaction. No user acceptance, production installation or publication is requested.

## Implemented

The Linux central installer can extend exact known managed Caddy definitions to
the existing local-peer-only agent routes. `--devices` offers the separately
reviewed transition when pairing encounters old ingress; no enrollment code is
issued until a real pinned TLS capability probe succeeds. Existing ports,
hostname, certificates, Core identity, Space and runtime images are preserved.
Unknown custom configuration is refused, not replaced.

The existing installation lock and root-owned journal record Core approval,
actor/Space IDs, host binding, exact before/after bytes and a transaction UUID.
Actual Caddy validation precedes the first change. Interrupted publication and
activation resume the same transaction. Local root can explicitly restore only
the previously approved configuration when Core is unavailable. Recovery verifies
the original TLS listener; it does not claim that an unavailable Core is healthy.

Pending work fences ordinary setup/startup/update/backup operations. Temporarily
using installer journal format 2 makes historical format-1-only binaries refuse
unfinished transitions. Successful activation or recovery restores format 1.
This is not a database migration. Enabled installed maintenance workers must
separately advertise the ingress fence after integrity/ownership verification;
downloading a new installer does not upgrade installed workers.

## Developer evidence

- Installer suites passed: 526 reported Windows tests and 545 reported Linux
  tests, twenty platform skips each. Ruff and changed-file formatting pass;
  workflow YAML and embedded Python parse. Core source is unchanged from its
  218-test security/gateway run (one skip); Linux agent retains 77 passing tests.
- The actual default Compose fixture passed with current Core schema 51,
  PostgreSQL, Web and Caddy. Only the owned Caddy container was recreated; the
  other three container IDs stayed unchanged. Core permissions, Caddy validation,
  local pinned TLS, reviewed extension during pairing and real code issuance
  were exercised. No successful provider/Core/proxy response was mocked.
- An injected interruption after the actual atomic file replacement resumed
  under the same UUID. A real Core outage left the operation pending and the
  original configuration/TLS listener was recovered without Core. Subsequent
  real login confirmed the same identity; managed keys remained unchanged.
  Legacy proxy configuration was deliberately reseeded between fixture cases.
- Actual frozen Linux binaries proved old-worker refusal, new-worker acceptance,
  old-installer reading of completed format 1 and refusal of pending format 2.
  The scheduling policy and pending metadata in that test were explicit fixtures;
  no actual scheduler was registered by that compatibility test.
- Core JAR SHA-256 is
  `998ddd7a7e88d99a052ada709882fcf83f3e6022aec149749c45ad1853057f00`.
  Local reports are `build/isolated-linux/agent-ingress-compose-report.json` and
  `ingress-worker-compatibility-report.json`.

The private native checkpoint `0.0.0-dev.20261115.13` built and passed version,
channel and public-CA smoke checks for Windows/Linux AMD64. Its metadata matches
the checkpoint sources before the subsequent strict malformed-worker-policy
check. The Windows one-directory service host built with its full source map.
These unsigned, unpublished builds do not establish target service acceptance.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Windows AMD64 executable | 12,886,750 | `6667144a0782d00bade306b855232e4f2a25adee23436554584c00de1c5fdb5f` |
| Linux AMD64 archive | 14,693,455 | `0a27b7b220347ca557b69f8750ce1983b214b7cc35401e861a7d5010edadd781` |

## Continuing work and limits

The same full transaction also passed locally in a fresh private Docker daemon
and private containerd, with separate mount/network namespaces and no default
route. The actual default Docker socket is rebound only inside that private
mount namespace; the install runtime intentionally ignores environment overrides.
The host daemon is not stopped or pruned. Only exact marker-owned test projects
are stopped. Runtime data and logs are retained locally; CI uploads summary JSON
only. Evidence: `build/isolated-linux/ingress-private-daemon-report.json`.
The manual Linux workflow includes the reproducible image-build/test job;
hosted execution has not been triggered.

Native Windows ingress transition is still missing adapter code, not merely
hardware acceptance. Windows prepared-node storage/service, complete task
placement and dependency validation, exclusive handoff, distributed AI/voice,
and node backup/update/data removal also remain implementation work. Existing
Linux tests do not establish ARM64, Windows SCM or physical cold-boot acceptance.
R23-R29 remain open in the binding requirements ledger.

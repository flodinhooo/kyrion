# Frozen installer prepared-node checkpoint

The complete installer assignment remains open. This checkpoint adds actual
foreground device operations to the downloaded installer, not a complete node
service installation or a request for user acceptance.

## Behavior

The source archive and native/service-host builders seal nine explicitly
enumerated modules from the existing gateway component. They do not copy a second
source tree into the repository or add a Python runtime dependency on the target
for native executables. Source hashes include the original component files;
compilation uses immutable staged copies. Unknown sibling paths, secrets, caches
and tests are excluded. Source-archive node imports also work without access to
the checkout or build-only packager module.

On the tested Linux path, `--prepare-node` displays the actual local system probe,
Core URL, certificate fingerprint and protected configuration destination. Only
`PAIR` starts the existing protected enrollment. A reviewed fingerprint is passed
into enrollment and checked before publishing copied trust/pending secrets, so
changing the source certificate after review cannot replace the selected trust.
Existing pending enrollment can resume without re-entering its secret. An
existing final identity is never silently overwritten.

`--node-heartbeat` requires explicit confirmation and sends one real report from
the target. It does not poll device commands or start microphone recording.
New schema-51 prepared devices have no task permissions until an authorized
administrator assigns them. Windows prepared storage is explicitly refused;
the Windows central installer remains a distinct supported implementation path
with its existing separate operating-system acceptance limits.

## Verification and platform limits

- Windows installer suite: 505 tests, nine platform-specific skips. Linux isolated
  installer suite: 513 tests, twenty platform-specific skips. Ruff passed.
- Agent protected-storage tests exercise a changed confirmed certificate, lost
  response, same-credential acknowledgement, private permissions, concurrent
  enrollment, retargeting refusal and existing-config preservation. Windows full
  agent suite: 29 passed, twelve Linux-specific skips; Linux agent suite: 41 passed.
- An actual frozen Linux installer executable `0.0.0-dev.20261115.3` paired with
  actual Core schema 51/PostgreSQL over verified local TLS. It reported target
  health, rejected repeated enrollment without overwriting the identity, retained
  credentials over a Core process restart, and failed after authenticated device
  revocation. Codes and credentials were absent from captured output.
- Only terminal choices were supplied through a pseudo-terminal. The fixture did
  not inject successful Core/agent responses. No external provider/browser login,
  microphone capture, household-device action or operating-system agent service
  installation was performed.
- Native Windows and Linux AMD64 builds and smoke probes are available as private,
  unsigned, unpublished development artifacts. ARM64, physical cold boot and
  Windows node-service acceptance are not claimed. The Core JAR remains a separate
  runtime artifact, not part of the installer executable.

| Native development artifact 0.0.0-dev.20261115.3 | Bytes | SHA-256 |
| --- | ---: | --- |
| Windows AMD64 | 12,826,188 | `c739f9f3750e0e5f373dd9dc01932039302d2ea56e2779a65524144d80fbe60a` |
| Linux AMD64 | 14,632,526 | `f2819d8da0cc5bc7d423a9bf637f7b04486a2ff1208a5252d1628a83804761fd` |

Both native build source snapshots match the current checkpoint, including all
nine gateway module hashes. Version/channel/public-CA smoke checks passed. The
existing Windows one-directory service host was also built with the same version
and source snapshot. Its executable smoke/version checks passed; service
registration and cold boot remain explicitly unaccepted.

`tests/integration/verify-installer-node.py` is the repeatable isolated fixture;
it takes the actual installer/Core paths and SHA-256 values, Java/PostgreSQL tool
paths and a private work directory. Its network namespace must be created by the
caller. The existing manual Linux CI workflow includes this frozen-node fixture;
hosted execution has not been triggered by this work.

## Next implementation work

Prepared-node service installation with dedicated least-privilege ownership,
policy-aware background operation/reconnection, owner-facing pairing-code export,
reviewed extension of existing proxy configurations, Windows prepared storage,
distributed AI, exclusive task handoff and local management UI remain source work.
Foreground enrollment and task permissions do not complete R23-R29. All other open
rows in the binding requirements matrix remain in scope. No user test handoff,
product publication or productive installation has occurred.

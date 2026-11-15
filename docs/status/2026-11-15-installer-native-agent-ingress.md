# Native Windows agent ingress transaction

The complete installer assignment remains open. ADR 0089 extends the existing
transaction to the native Windows backend. This is implemented source with
partial real Windows API/process evidence, not accepted elevated SCM support.

## Implemented

Native setup and maintenance now share exact Caddy definition generation. Known
legacy and pre-task routes can be extended without changing the listener, keys,
virtual accounts or dependency graph. The same CLI, Core approval, installation
lock, transaction UUID, journal phases, continuation and recovery are used.
Unknown custom bytes and mismatched files are preserved/refused.

A Windows DPAPI local-machine protected purpose/installation marker binds the
transaction to its operating-system installation. It is not an account secret or
per-user authorization mechanism; the protected journal and existing native
permissions remain necessary. Public proxy replacement uses exclusive native
file creation with the existing runtime configuration's owner/group/DACL.

The installed service-host payload is integrity-checked and must advertise native
ingress protocol 1 before any transaction begins. Enabled maintenance executables
are separately checked. A new downloaded installer does not upgrade them. Pending
journal format 2 is recognized narrowly by the runtime and native permissions
helper; ordinary maintenance remains fenced. New activation permits only Caddy
against the exact approved replacement. Recovery permits Core/Web/Caddy only
after the exact original configuration is restored. Authority retirement, restore
and update fences remain in force.

SCM startup can start stopped dependencies; the bilingual review explicitly says
so. A dependency failure leaves the operation pending. Restored file bytes do not
constitute verified recovery. There is no desktop-login substitute or dependency
graph rewrite. The previous exact-capability updater regression was separately
fixed and tested in [the compatibility checkpoint](2026-11-15-installer-native-capabilities.md).

## Evidence and acceptance boundary

- Installer suites passed: 542 reported Windows tests/twenty skips and 561 Linux
  tests/twenty-five skips. Ruff, changed-file formatting and manual workflow YAML
  checks pass. Core and gateway sources are unchanged from their recorded tests.
- Actual Windows NT 10.0.26300 DPAPI calls passed round-trip, wrong installation,
  damaged data and canonical encoding checks. Actual private Windows files passed
  interrupted publication, journal reload/format barrier, same-UUID continuation,
  original recovery and refusal when secured file creation fails.
- In these private file tests, administrator authorization, deployment ACL
  verification and SCM lifecycle are explicitly test doubles. They do not prove
  virtual-account access, machine-to-machine refusal or installed-service startup.
  Existing native ACL API tests remain separate actual user-file evidence.
- A manifest/hash-verified actual Windows Caddy binary validated both managed
  definitions and refused malformed configuration. No server/service was started
  by this CLI validation fixture. Report:
  `build/native-agent-proxy-validation-report.json`.
- The existing disposable elevated Windows service fixture now exercises actual
  Core permissions, retained service hosts and enabled maintenance workers,
  normal proxy-only restart, interrupted publication/resume, actual Core service
  outage and original recovery through stopped SCM dependencies. Its only DNS
  substitution maps the fixture hostname to loopback; fault timing is explicit.
  This hosted fixture/workflow is prepared but has not been executed here. It
  cannot be reported as a passing SCM or pre-login boot acceptance result.

## Continuing scope

Private native artifacts `0.0.0-dev.20261115.15` built successfully; both pass
version/channel/public-CA smoke checks. Every sealed installer source hash and
the Windows one-directory host's full source map match this checkpoint. The
actual built Windows service host advertises native ingress protocol 1 and the
pending-operation fence. No service dispatch was invoked by that check.

| Private artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Windows AMD64 executable | 12,897,694 | `00a584fe1dd7207845d0b112b0e1668159b7f0c505d38a7c7802d4f6ad8867a8` |
| Linux AMD64 archive | 14,706,046 | `901301f10ee41e538886a7285f3bc49a5cf06163bb40014f15ee28c054bb9fd4` |

Metadata: `build/native-agent-ingress-final-artifact-report.json`. All
development artifacts remain unsigned and unpublished. Full Windows service/
virtual-account acceptance requires the disposable elevated test environment;
physical boot and ARM64 remain unaccepted. Prepared Windows target storage and
service, complete task placement/dependencies, exclusive handoff, node update/
backup/removal and the remaining binding ledger continue as source work.

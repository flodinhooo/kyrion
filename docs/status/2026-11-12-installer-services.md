# Installer continuation: native Windows services

The complete installer task remains open. This is a continuation checkpoint,
not a request for user acceptance. The authoritative scope is
[the full requirements ledger](../installer-requirements.md).

## Implemented source

- ADR0050 and native SCM plans/host: dedicated virtual identities, fixed commands,
  protected management ACL, dependency order, bounded recovery, job-contained
  descendants, real readiness and stop handling.
- Atomic private installation journal, authenticated private download staging,
  no mutable-source extraction; initial database uses a temporary demand-start
  service under the eventual database identity and is promoted only after checks.
- Native configure/provision, repeat/resume, repair and data-preserving or
  explicitly destructive uninstall using the existing journal and Core APIs.
- Independent internal Core/Web TLS keys, pinned clients, process-scoped Node
  trust, and connected-peer PID verification before forwarding decrypted Web
  traffic. No global trust store changes or disabled TLS verification.
- Frozen one-file installer and one-directory SCM host with allowlisted public
  files and runtime legal notices; schema-3 payload builder and pinned vendor
  assembler; ephemeral development signing without persisting a private key.
- Manual disposable hosted Windows service acceptance workflow; it builds the
  real stack and tests actual service identities/ACLs, repeat and repair/restart.
  It has not been dispatched or published.

## Actual developer verification

- Windows 11 x64 build 26300: 125 Python tests pass, one symlink skip. Native
  read-only SCM, token, descriptor and TCP ownership SDK calls were exercised.
  The full suite needs the normal developer context for read-only scheduler COM;
  no service or task was registered on this host.
- Isolated Debian 13 x64 WSL guest: 125 tests pass, 13 platform skips. Its Windows
  drive mounting and interop are disabled. Existing WSL distributions and Docker
  containers were not started or changed. This is not Linux system-boot testing.
- Actual native PostgreSQL 17.11-5 / Java 21.0.13+9 / Node 22.23.3 / Caddy 2.10.2:
  fresh database, 48 Core migrations, synthetic owner/Space, pinned Core and Web
  TLS, verified child connection, process restart/login and closed bootstrap
  pass (`build/windows-native-tls-20261112.json`). The sandbox cannot create the
  PostgreSQL restricted child token; the test passed in normal developer context.
  No services/tasks were registered and no cold boot is claimed.
- Changed Python modules pass Ruff. Actual new one-file and one-directory builds
  pass native smoke; the resulting EXE verifies the newly test-signed schema-3
  bundle without invoking an external OpenSSL executable.

## Local development artifacts (not published)

| Artifact | Size / hash |
| --- | --- |
| `build/native-installer/kyrion-installer-0.0.0-dev.20261112.3-windows-amd64.exe` | 12,293,211 bytes; SHA256 `af8a0824e543f2bae265c7a053fdd8b20dff5fc77460ffe2b3f67752efd8aefc` |
| `build/native-service-host-dev3/` | one-directory direct-process SCM host; source hash inventory in `build-source.json` |
| `build/windows-service-bundle-dev3/kyrion-windows-amd64.zip` | 224,264,886 bytes; SHA256 `87714eb4bf834ecd7e15cb2f000e07523e9c70d1992e79fb5bd7bff3f8f26e35` |
| schema-3 manifest | SHA256 `a9e9778ea367147b416035c49128cb1bbad00ff656cd78277a005fba5d203ce0`; 6,008 files |

These are unsigned Windows executables and test-authority signed runtime data,
not production downloads. The pinned vendor versions are development inputs;
review current upstream security releases before any public release. Productive
signing/trust, repository redistribution licensing and publication authorization
remain external requirements.

## Continue without user handoff

Actual service registration, virtual-account ACL normalization and host boot
acceptance need a disposable elevated Windows environment. The current token
is not elevated; no UAC prompt or host service mutation was attempted. The CI
fixture automates that acceptance when an authorized runner is available.

Do not confuse that test boundary with missing product code. R08, device pairing
and safe task moves, regular directly linked account onboarding, full authorized
Space selection, hardware/catalog integration, Ollama lifecycle, Velora,
transactional installed updates, full application restore and the adaptive
tutorial still require implementation. Continue those independent tasks against
the existing Core authority, then run complete isolated journey tests. Never
describe this checkpoint as ready for the user's overall installation test.

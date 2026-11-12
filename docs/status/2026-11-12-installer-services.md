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

## Further implementation in the same continuation

Windows recovery now invokes the existing Core host-only tool with the real
console, stops only validated owned Core/Web/Caddy services, preserves existing
keys and restarts services even on tool failure. Four orchestration tests pass;
interactive elevated execution/ACL acceptance is explicitly still unverified.

Authenticated model-catalog refresh is wired into local maintenance and the
existing journal. Signed HTTPS input, accepted sequence, digest and public trust
are published atomically; stale sequences, same-sequence changed payloads,
tampering and trust-epoch rollback are refused. Installed recommendations read
the verified cache after restart without networking. An expired bundled catalog
does not prevent refreshing; expired cached data is not silently downgraded.
Skipping AI does not load the catalog. This is manual refresh, not an automatic
scheduled feed or public release infrastructure.

The extended full suites passed 135 tests on Windows (one skip) and Debian 13
(13 skips). Two additional catalog-expiry regressions subsequently passed on
both systems as part of the eight-test signed-cache suite. The final Windows
full suite passed all 137 tests (one platform skip). Ruff passed for all
new/changed modules. The new build is `0.0.0-dev.20261112.4`; earlier artifact
rows above describe the reproducible service checkpoint and remain historical.

| Latest local development artifact | Size / SHA256 |
| --- | --- |
| `build/native-installer/kyrion-installer-0.0.0-dev.20261112.4-windows-amd64.exe` | 12,298,847 bytes / `4b97c00bffd873ee0d58de67c583909b2033ed6aaa2d606cbd9fd54a3d92cdaf` |
| `build/native-service-host-dev4/` | updated frozen host with exact source inventory |
| `build/windows-service-bundle-dev4/kyrion-windows-amd64.zip` | 224,268,185 bytes / `5a7f6863e60e9180a33a69cac44ef09bd748f6e409ac97bac5e34cb7cfa502bf` |
| schema-3 manifest | `9430785071c91d4be8dadeb0a97c781394f22faca595fabbf1bbbd6d793f5a3f` |

The latest EXE and host native smoke pass. Public download/service acceptance
is still false. Remaining whole-product source work listed above is unchanged.

## Atomic Windows file security correction

Further source review found that replacing a journal with a normally created
temporary file would drop its explicit runtime read grants and administrator
ownership. Initial managed files could likewise acquire the interactive
administrator's owner SID before policy assignment. This would break the first
real service acceptance and is a source defect, not an external test limitation.

New managed/temporary files now use exclusive CreateFileW with owner/group/DACL
in SECURITY_ATTRIBUTES before writing. Journal replacement copies the original
protected descriptor before publication. Three actual Windows SDK tests prove
exclusive creation without truncation, descriptor preservation and failure
before replacement. The current full Windows suite passes 140 tests (one skip).

Development artifacts up to `.20261112.4` above are historical and superseded;
do not use them for SCM acceptance. The corrected standalone build is
`build/native-installer/kyrion-installer-0.0.0-dev.20261112.5-windows-amd64.exe`,
12,302,284 bytes, SHA256
`b6eafcd6e90c9f12c2fae5f4d5f28b9d243492a97fbc7c4964d1b0ece104abb6`.
The corresponding direct host is `build/native-service-host-dev5/`, with exact
source hashes in `build-source.json`. Both native smoke tests pass. This still
does not claim actual registered-service or boot acceptance.

The final corrected Debian 13 full suite also passes 140 tests (16 Windows-only
skips), using the same current source. The guest is the isolated fixture named
in `build/isolated-linux/fixture.json`; mounts/interop remain disabled.

The corrected schema-3 runtime bundle is
`build/windows-service-bundle-dev5/kyrion-windows-amd64.zip`, 224,271,856 bytes,
SHA256 `c51846381373d53fcc902844fd812b5103af3e6a7587e45597e0569c1d9b2a95`.
Its manifest hash is
`3ec09df1557f2d0886aa99eeab1036d778705109930c31aa2e1c055637c13ba0`.
The built EXE verifies its ephemeral test-authority signature. Private test
signing material is not persisted; no artifact has been published.

# Installer continuation — developer evidence and open work

The full installer assignment remains open. This is a continuation record, not
a product acceptance or a request for the owner to test partial features.
The binding scope is the [requirement matrix](../installer-requirements.md).

## Source and environment

Work continues on `master`. Baseline `1c3bcee` preserves the pre-existing guided
installer changes. Subsequent task commits were inspected and retained. No
reset, worktree, production deployment, publication, paid API call or household
device action was performed.

Available developer environments: Windows x64/Python 3.12.1/Node 22.21.1,
isolated Debian 13 Python containers, and isolated Java 21 containers. Docker
tests use newly labelled resources, synthetic secrets, exact image IDs, and
cleanup of only resources created by the test. Offline mode publishes no ports;
browser mode exposes only an ephemeral 127.0.0.1 port in a separate bridge network.
The browser mode is not an offline-network acceptance test. Target
hardware, host cold boot, Windows background-service provisioning and ARM64
installation acceptance have not been established.

## Implemented during continuation

- Bilingual website download/help and optional hardware advice. Public catalog
  remains empty until accepted, signed artifacts actually exist in a published
  release. Strict metadata validation and read-only catalog generation prevent
  draft or invented downloads.
- Native PyInstaller build and executable probe, with target-platform CI jobs.
  Windows development EXEs and a Debian 13 x64 standalone archive were built and
  executed. They are unsigned development artifacts, not platform installation
  acceptance. Manual Python installation is not required to run these binaries.
- Durable pending-write recovery adopts only exact recorded bytes after an
  interrupted secret write. Tampering and blind copied-install adoption fail.
- Scoped signed-document verification, trust rotation/replay protection and
  platform/API/schema compatibility selection for update discovery. Installed
  scheduling and applying updates remain missing.
- Consistent Core-paused database/config/key/knowledge capture, GPG encryption,
  bounded archive validation and actual restore into a new isolated PostgreSQL
  database. Full restored-application activation and identity fencing remain
  missing; database restore is explicitly not application restore acceptance.
- Maintenance commands for known-original nonsecret repair, data-preserving
  uninstall with separate purge consent, and allowlisted local diagnostics.
- HOME/BUSINESS onboarding and wrapper for the existing host-only Core recovery
  tool. Interactive recovery acceptance remains unperformed. Regular required
  linked-account onboarding and existing authorized Space selection remain open.
- Home Assistant selected-device/entity previews, revisioned persistence, room
  overrides, encrypted credential reuse and explicit single-power-entity control
  consent through the existing Core command/authority/audit boundary. The local
  Web card and terminal assistant collect selection and consent. Service calls
  are fixed light/switch power operations followed by a confirming state read;
  saving selection does not call a service. Legacy unselected imports remain
  read-only. See ADR 0047. Synthetic full-stack verification passes with the
  current source-built Core and Web images.
- Optional hardware-based model questionnaire, reviewed exact Qwen3 variant
  metadata and conservative resource recommendations. Updated data verifies
  through the existing scoped Ed25519 policy. Automatic signed catalog refresh,
  persisted antirollback and full Ollama lifecycle remain open. See ADR 0048.

## Developer checks

- Installer Python suite: Windows 83 tests, successful with one platform skip
  (forbidden symlink creation). Debian 13 isolated run: 79 tests,
  successful with no skips.
- Windows boot-task groundwork uses the real scheduling API for definition
  validation and read-only lookup of a random absent task. Four additional
  tests pass outside the constrained sandbox; its root-folder query is blocked
  inside that sandbox. No task registration/start/removal was performed on the
  owner's host. The native logon API, boot trigger, task-specific token SID,
  retry/duplicate settings and input-plan protection are checked. Registration
  and complete native installation remain unaccepted. See ADR 0049.
- Native Win32 exclusive file-handle locking is now implemented and actually
  checked on Windows, including exclusion of a second process and release after
  exit. The existing POSIX lock has the same cross-process regression. This is
  Windows orchestration groundwork, not complete Windows provisioning.
- Java 21: 20 targeted Home Assistant/device-command tests pass, boot JAR built.
  Test XML is in ignored `build/core-fixture-output/test-results/test`.
  An unfinished Mockito stub and an outdated audit-source assertion were found
  and corrected before the successful run. An actual production-Jackson request
  issue with omitted stored credentials was reproduced and fixed with nullable
  optional fields; the production-generation mapper regression test passes.
- New local Web selection contract: two tests pass. Changed Web source passes
  TypeScript and ESLint. Production build initially failed because sandbox
  network policy prevented existing Google Font downloads; the network-enabled
  retry passes. A fresh source Docker Web build also passes.
- Website: production build, types, lint and 13 browser/catalog tests passed.
- Actual GPG encrypted backup roundtrip/wrong-password refusal and isolated
  PostgreSQL dump/restore were exercised again, including expected user/Space/
  audit counts. The current full stack verifies TLS,
  fresh owner/Space setup, persisted local login after Core/database restart,
  and bootstrap remaining closed. This is process restart, not host cold boot.
- Current HA full-stack run passes with source-built Core image ID
  `sha256:8b7df2d2419f1eab99ee2e975aa90e91a1475af49d41631827913eeb1f0e61a0`
  and Web image ID
  `sha256:e202e2b362509ad2b16550a60e7475da32b3d4fa298fa67e27e7bd56eeb16a6b`.
  It checks selective entities/import, optimistic conflict, no action on saving,
  explicit fixed-service power action, state confirmation, removed entity and
  deselection. The provider is a synthetic HA-compatible API, not physical HA.
- Real Chromium checks also pass in German/English at 1440/390 pixels against
  those actual Core/Web/DB containers: selection, explicit control consent, room
  override, confirmation dialog and persisted selection. Both browser request
  tracing and the synthetic provider's service-call counter verify that saving
  causes no device action. The fixture's disposable browser context accepts its
  self-signed certificate temporarily; independent curl checks verify TLS using
  the actual generated leaf certificate. No product TLS setting is relaxed.
  Default offline mode remains internal-network/no-ports. Browser-mode isolation
  and DNS/route restrictions are separate and explicitly reported. CI now prepares
  the existing Playwright tooling and runs both modes; hosted CI was not triggered.
- Native Windows development artifact `0.0.0-dev.20261111.4` was built and its
  complete model recommendation questionnaire was actually executed in a PTY,
  without Python as an end-user requirement. No model download occurred.
  Metadata reports native smoke success and platform installation acceptance
  false. Linux x64 archive of the same source was also built and executed in
  Debian 13. Development artifacts are under ignored `build/native-installer`
  and `build/native-linux`; neither is signed or publicly offered.
- Ruff passes for changed Python modules. Broad Ruff additionally reports old
  issues in `configure.py` and `tests/test_installer.py`; they are not hidden by
  the successful targeted check.

## Immediate continuation

Retain the successful synthetic HA API/browser scenarios as regressions and
continue with the open matrix rows rather than handing the partial implementation
to the owner. Core/Web HA source is saved in local commit `a4ca331`; model planning,
maintenance safety and the continuation evidence are saved in `711cd14`.

The major open implementation groups are Windows runtime/service installation,
device enrollment/task movement/fencing, regular linked-account/Space onboarding,
hardware detection, remaining integrations, AI/Ollama/voice provisioning,
installed update transactions/scheduling, full application restore, and adaptive
tutorial/final checks. Missing target hardware does not excuse these missing
source implementations.

Windows continuation: implement the authenticated native runtime bundle,
administrator-owned ACL/bootstrap state and controlled child supervision; then
connect the actual provisioning/maintenance flow and automate task/service
registration in a disposable Windows runner/VM. `windows_tasks.py` and its fixed
PowerShell helper contain real task operations with strict name/definition,
journal, binary-integrity and ACL ownership checks, but they are not yet wired
into the normal installer. They do not constitute completed matrix R20.
The helper's execution-policy flag is confined to its child process; no machine
or user execution policy is changed, and enforced Group Policy is not overridden.


## Native payload continuation evidence

The full task remains open. Current source passes 97 installer tests on Windows
(one symlink-permission skip) and Debian 13 (one Windows COM skip). Windows COM
validation is read-only and requires the less restricted developer execution
context; no service or task was registered. Changed Python files pass Ruff.

Signed manifest review now uses the exact immutable verified bytes; Linux OCI
archives are privately staged with streaming digest checks before Docker load.
Tests cover changing original source archives and interrupted private staging.
The new native payload builder/validator performs bounded exact per-file/PE
checks, exclusive extraction, crash resumption and compact receipt migration.
Twelve native payload tests use explicitly synthetic PE files without execution.
See [the native contract](../installer-native-windows.md).

Actual vendor runtimes downloaded into ignored development directories were
executed successfully: Temurin JRE 21.0.13+9, Node 22.23.3, PostgreSQL 17.11-5,
Caddy 2.10.2 (Windows x64). Three upstream checksums matched independent official
vendor metadata; PostgreSQL's observed checksum was recorded after the official
EDB HTTPS download, without claiming an independently published vendor checksum.
The local Web standalone application was separately built on Windows from clean
public source, with no `.env` or private provider configuration. The clean public
runtime/application profile contains 5,960 files. The unsigned development ZIP
is 212,048,954 bytes, SHA-256
`20d377dffe20e127fcfb0278e4865a6082d0d7061f86ce6c7a15e16e8ce52d61`.
Only an ephemeral development key signs the extraction test; production keys and
release acceptance remain absent. No public release or download was activated.

The real large-payload extraction was deliberately interrupted, revealing an
orphan atomic-journal temporary and an inefficient growing progress list. Both
cases now have regression tests. Actual extraction resumption is in progress;
the native-stack runner is prepared but has not yet supplied passing evidence.
Do not treat executable version probes or the archive as complete Windows R20.

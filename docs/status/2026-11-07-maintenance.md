# Maintenance verification ? 2026-11-07

Scope: source-only maintenance on existing `master`, starting at `3170737` with a
clean working tree and one registered checkout. Existing personal processes and
installations were preserved. No push, deployment, DNS/identity configuration,
provider request, paid service, real release key or hardware action was performed.

## Changes

- CI push/PR targets are `master`; manual dispatch remains. Java 21, Node 22.21.1,
  pnpm 10.29.3 and Python 3.12 are explicit. Existing action pins and read-only
  contents permissions remain; newly used actions are also pinned to resolved
  official commits. Core builds the required schema-rehearsal artifact before
  tests. Hosted Ubuntu supplies Docker/Testcontainers; no shared DB is used.
- AI, Gateway and Satellite each run declared dev-extra installation, Ruff,
  pytest and sdist/wheel builds. No Python lockfile exists; no dependency range
  was changed. Web and Website install their existing frozen pnpm lockfiles.
  Website runs lint, format, type generation/check, production build and Chromium
  tests. Optional live identity/physical/provider runs remain separate; no existing
  integration suite was disabled. The opt-in Core live-provider smoke is unchanged.
- Release builds explicitly prepare ARM64 emulation/buildx and Python; signing
  checks out its scripts, has a timeout, and manual version input passes through
  an environment variable before validation. Signing remains protected and
  publication remains disabled. No release build/signing/publication was attempted.
- All 24 maintained POSIX entry points (Gradle wrapper, Installer/release and node
  operator scripts) are Git mode `100755` with LF. All have `#!/bin/sh`; none is a
  source-only library. Historical `.run` scripts are untouched. Attributes enforce
  entry-point LF and stable website/workflow formatting across checkouts.
- Gateway lint fixes only reorder an import and wrap long expressions. Two
  polling unit tests now stub the unrelated MQTT subscriber target: the Linux run
  exposed its background retry racing the shared sleep mock. Polling/backoff
  assertions remain; no integration test was removed or weakened.
- [TODO](TODO.md) is the active backlog; old TODO, status index and chat context
  are preserved as explicitly named archives, verified against baseline Git blobs.
  Current README/status/context/roadmap distinguish implementation, automatic
  testing, deployment, physical/provider acceptance and plans.
- Public DE/EN Home, Product, Private/HOME, Business and Development copy now
  covers integrated Spaces/roles/invitations, optional central accounts with local
  login, joint household events, voluntary disclosure/manual Google delivery,
  Knowledge and Velora limitations. About, Docs, Contact, Account/legal pages and
  CTAs were reviewed. Existing routes/design are retained. Tiny existing formatting
  deviations were corrected; build outputs are excluded from Prettier. Consumer
  release, multi-Space, Business Voice, public identity and real acceptance are
  explicitly limited rather than advertised as complete.

## Executed verification

| Check | Result |
| --- | --- |
| Workflow schema/expressions | actionlint 1.7.7, both workflows pass; downloaded tool SHA-256 checked. ShellCheck was unavailable; `-shellcheck=` disables only that optional external analyzer. |
| Core | Java 21 `bootJar`, then complete `test --rerun-tasks`: **449 recorded, 0 failures/errors, 1 existing opt-in real-Keycloak smoke skipped**. Includes real disposable PostgreSQL migration/restore integration tests. Build successful, 8m48s for full test invocation. |
| Web | Frozen install, ESLint, `tsc --noEmit`, **262 tests**, production build pass. |
| AI | Fresh dev install, Ruff, **172 tests**, sdist/wheel pass on Windows and Linux. |
| Gateway | Ruff, **17 pass/1 Linux-only skip** on Windows; complete Linux **18 pass**, sdist/wheel pass. |
| Satellite | Fresh dev install, Ruff, **77 tests**, sdist/wheel pass on Windows and Linux. |
| Installer | All **3 tests** pass on Windows and Linux; Python compilation and shell syntax pass. Compose `config --quiet` passes with isolated placeholder paths. |
| Git modes/signatures | Index-derived tar preserves all 24 `100755` modes and LF; extracted in a network-disabled Linux container, `test -x`/shell syntax and signature tests pass **without chmod**. Fresh disposable Ed25519 key accepts valid manifest and rejects modified manifest. |
| Website | Frozen install, ESLint, Prettier, typecheck, production build and **40 Chromium tests** pass on final source. Includes DE/EN routes/metadata, links, responsive navigation, themes, no-JS/reduced-motion and SMTP-disabled contact cases. |
| Visual inspection | Playwright screenshots inspected for German mobile HOME and English desktop Business; navigation/content/overflow checks cover desktop, tablet and mobile. No public site was changed or used as the test target. |

Local toolchain: Windows Node22.21.1/pnpm10.29.3, JDK21.0.13 and Python3.12.1;
additional Linux checks use disposable Python3.12 containers with synthetic data.
Builds use `.next-maintenance-build`, never the running Web/Website artifacts;
local generated TypeScript build includes are removed from the final source.
Private, ignored logs are under `.run/private-evidence/maintenance/`.
Both pnpm lockfiles and all Python dependency declarations remain unchanged.
The final explicit Business Voice guard assertion also passes its targeted
DE/EN desktop/mobile audience test.
Final relative-link checks cover 103 links in the edited active documents with
zero missing targets; the archived snapshots also have no missing file targets.
DE/EN locale keys, array shapes and types match. Git whitespace and mode checks pass.
No secrets, local databases, model files or generated build outputs are staged.

Linux matrix runs use a tracked-source-only archive, separate venvs and the
versioned Voice assets/operator modules required by the tests. Initial incomplete
archive attempts failed collection because those fixtures were omitted; the full
tracked fixture runs pass and match the complete CI checkout layout.

The first Gateway Linux run failed the real test race described above and passed
after correction. Initial format checks included old generated builds and existing
formatting deviations; the ignore/format corrections pass. A PowerShell wildcard
`py_compile` invocation and an inline Linux shell argument failed as tooling
invocations; explicit Python file iteration and a script-file invocation passed.
These failed attempts are not counted as successful tests.

## Boundaries and reproduction

No hosted GitHub run was triggered or claimed. Protected release signing, clean
ARM64 installation, public central identity, authenticated real family/provider
journeys, physical audio/devices and full-host/off-host recovery remain open in
[the active backlog](TODO.md). Local tests do not substitute for those gates.

Reproduce Python checks per component with `python -m pip install '.[dev]' build`,
`python -m ruff check .`, `python -m pytest`, `python -m build`.
For Core, run `./gradlew bootJar`, set `KYRION_MIGRATION_REHEARSAL_JAR` to the
absolute generated JAR path and `KYRION_MIGRATION_PYTHON=python`, then run
`./gradlew test --no-daemon --console=plain` with Docker available. This builds
and tests synthetic fixtures only; do not supply personal connection settings.
Web commands are in CI; [Website commands](../../apps/website/README.md) include
isolated browser startup. The signing test creates and removes its own test key.

# Consented Linux backup prerequisite, 2026-11-14

The full installer assignment remains open. This addition closes the previous
missing GnuPG package-bootstrap code for Debian 13 AMD64/ARM64; ARM64 package
execution remains untested. It does not install Docker or constitute complete
clean-host Kyrion/system-boot acceptance.

`linux_crypto.py` reuses the protected installer journal/lock and APT. It checks
administrator/host/file/authority state, root-owned fixed executables and the
actual GnuPG tools, including the agent. Existing tools are reused. There are
separate explicit confirmations for repository-metadata refresh and exact
package/version/download/allocation review. No repository/key addition,
authentication bypass, removal, existing-package upgrade or global repair is
performed. Required new packages are pinned and the solver is rechecked before
mutation. Raw repository output is temporary/private, never part of diagnostics.

Phases are persisted before package changes. Interrupted approved downloads can
replenish the same version-bound APT cache. Recovery configures only explicitly
reviewed unfinished packages; unrelated incomplete work is refused. APT success
alone is insufficient: actual tool probes must pass. An incomplete owned intent
is resumed even if its executables already exist. Backup configuration offers
this path when needed; later use `--target TARGET --install-crypto`. Background
backup/update workers never install OS packages. An incomplete owned package
intent is refused before a new update transaction creates its startup fence;
backup service recovery still runs before that prerequisite check. Diagnostic export includes only
the allowlisted prerequisite phase, without package-manager output or URLs.

## Evidence

Thirteen journal/solver/permission-boundary tests explicitly inject APT/dpkg and
administrator observations. They cover refusal, pinned review, recovery,
unreviewed dependencies, no false readiness, ownership fences and existing tools.

`build/isolated-linux/crypto-prerequisite-tools.json` records real Debian 13
GnuPG/dpkg/APT simulation and existing-package reuse in the marked developer
guest. It makes no package-installation claim.

Actual fresh-package and acknowledgement-recovery evidence:
`build/isolated-linux/crypto-clean-install-cut-report.json`. A new Debian 13
chroot starts without GnuPG, obtains the real approved pinned packages through
APT, resumes the installer after a deliberately injected process exit following
successful APT but before journal acknowledgement, performs a real synthetic
GnuPG encryption/decryption roundtrip, then repeats without package changes.
This is **not** an interruption midway through dpkg, hardware power loss,
application backup/restore or physical/system boot acceptance.

The own chroot has an inode/device-bound private marker and no host package
changes. Separate mount/PID namespaces and a checked `policy-rc.d` prevent service
starts outside the fixture. Official Debian OCI manifest:
`sha256:7378260c0a098d27ac206225db5e7d92b8c7c84ea7afccc86eeb513756bbd392`;
rootfs layer:
`sha256:37fb86c2a767b88d500c6872195f88078f64765fe0d2f9cc375cc2efbd4c0a41`.
OCI digest/TLS provenance is developer-fixture provenance, not Kyrion release
signing. Synthetic private outputs are retained in the own developer guest.

The manual Linux CI now prepares/runs the same chroot test and exports its
report; YAML parsing passes, but the workflow has not been dispatched.
Full suites pass: **379 Windows tests (three skips)** and **381 isolated Linux
tests (16 skips)**. Reports: `build/installer-tests-20261114-linux-crypto-complete.txt`
and `build/isolated-linux/test-report-current.txt`. Ruff lint and workflow YAML
parsing pass. Native artifact evidence is recorded separately after packaging.

## Remaining boundaries

Fresh-host Docker/Compose setup, supported non-Debian package paths, native
Windows service/boot acceptance, application capture through the backup schedule
and distributed/full product journeys remain separate matrix entries. No
productive package changes, releases, keys or household operations were made.
Official package/command references are linked in ADR 0071.

Native `.20261114.7` Windows/Linux AMD64 developer packages were built and
smoke-executed; all raw packaged source hashes match the checked source.
`build/native-linux-crypto-package-report.json` records both checks. Windows EXE:
12,578,641 bytes, SHA-256 `175cffb36baa621fdc89ccc93569d802c74cfdc4199bc36b5abdac6d79eca619`.
Linux archive: 14,384,522 bytes, SHA-256
`6d313e4f53c9d8224e4511eb9faecb680971ab539aac88aa8b13cdb4af62023c`.
Artifacts/adjacent JSON are in `build/native-installer/`, unsigned/unpublished,
with `platformInstallationAccepted: false`. This does not claim native Windows
APT support; the new package action intentionally targets Debian 13 only.

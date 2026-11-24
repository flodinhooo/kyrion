# Windows prepared-node pairing entry

The existing downloaded installer now exposes protected foreground pairing and
an explicitly requested status heartbeat on native Windows amd64, NT major 10,
build 22000 or later. Actual developer acceptance is limited to NT 10.0.26300;
other builds admitted by that source check remain platform-unverified. Windows
task runtime and prepared-node SCM deployment are still rejected. These are
separate from the existing native central services. No background availability
or task deployment is claimed by pairing or a single acknowledged heartbeat.

The existing packet parser, reviewed Space binding, durable identity/acknowledgement
protocol and protected Windows file adapter are reused. The target runs its own
inventory. An explicit heartbeat reports the actual configuration volume and
native RAM observations with capability-gated unknown fields. Existing local
identity is not replaced. DE/EN review explains the scope and pending service work.

## Verification

- Actual Windows installer entry functions against immutable Core
  `1372862d1bef50803858a60f574c90486e77457b05e5028b746dd4f2108a0021`,
  fresh PostgreSQL and pinned TLS: private packet import, deliberately lost real
  acknowledgement, same identity on resume and explicit resource heartbeat pass.
  Linked BUSINESS identity, member restrictions and offline login after actual
  Core/PostgreSQL process restart also pass. OIDC provider is synthetic. Report:
  `build/windows-node-entry-report.json`. This is not SCM/cold-boot acceptance.
- Installer suites: Windows 545 tests / 20 skips; isolated Linux 564 tests / 26
  skips. `build/installer-windows-node-entry-tests.txt` and
  `build/isolated-linux/test-report-current.txt`.
- Packaged Python entry tests pass; actual frozen Windows binary in a real
  terminal reads a protected synthetic packet, displays the review and cancels
  with exit 0 before creating configuration. Verified only the original packet
  remained; the exact private fixture was removed without recursive cleanup.
  `build/native-node-cancel-report.json`. No Core enrollment was performed by
  this cancellation test. Missing configuration is correctly refused by the
  actual frozen heartbeat entry.
- Ruff and changed-file formatting pass. Both new native artifacts pass actual
  version/capability/probe smoke checks; their sealed source maps and SHA-256
  match the working source. `build/native-node-entry-artifact-report.json`.

## Private artifacts

Unsigned and unpublished, version `0.0.0-dev.20261124.1`:

| Platform | Artifact in `build/native-installer/` | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Windows amd64 | `kyrion-installer-0.0.0-dev.20261124.1-windows-amd64.exe` | 12918782 | `31cd68fb0eb3235ec390bcaca99cbc103ac558f1cab62408a55172c89c1ff6ea` |
| Linux amd64 | `kyrion-installer-0.0.0-dev.20261124.1-linux-amd64.tar.gz` | 14727003 | `49149ed53dc930dce9321140c3d22518b18189438100973e5499990879e69a49` |

They are development builds, not published/signed consumer downloads. No arm64
build or Windows boot acceptance was performed in this batch. Historical `.15`
artifacts retain their old scope and do not acquire these source changes.

## Next implementation

Complete the Windows scoped runtime and boot deployment using the existing
gateway/installer/native service architecture, then complete task placement,
dependency validation and exclusive handoff. Node backup/update integration and
the full requirement ledger remain open. No partial user acceptance is requested.

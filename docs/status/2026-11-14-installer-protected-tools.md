# Protected operational tools and real recovery regression checks

The full installer assignment remains open. ADRs 0077 and 0078 extend the
existing runtime and recovery paths rather than introducing another installer.
Linux Docker/OpenSSL/GnuPG operations use protected fixed OS tool locations and
minimal child environments. Missing GnuPG prerequisites fail before update fences
or service pauses. Frozen Windows never falls back to caller PATH GnuPG; its
portable dependency remains manifest-verified.

Plaintext restore scratch requires a private checked parent. Linux agent homes
use short private directories under checked system /tmp, ignoring caller TMPDIR.
Actual integration testing exposed UNIX-socket overflow when an agent home was
placed under a deep installation directory. The short-home correction passed the
real application update/recovery test, including encrypted backup, actual Flyway
49-to-50 migration, a failing migration, interruptions and database recovery.

Actual Windows portable GnuPG also failed with a 161-character home despite a
successful executable probe. Native agent homes now use exclusive protected
short directories below OS-resolved ProgramFiles. The 80-byte bound, ancestor
policy and administrator prerequisite are checked before password handoff.
Read-only testing found that ProgramData's ordinary Users create/write rights
(effective mask 0x116) conflict with the existing ancestor policy. The default
new-install root therefore uses ProgramFiles/Kyrion; no global ACL is weakened
and no existing installation is moved.

## Evidence and limits

- Windows: 440 tests pass, eight skips. Isolated Debian: 447 pass, twenty skips.
  Ruff lint and formatting of changed Python files pass. Nine previously
  unformatted unrelated files are left unchanged. Both installer CI workflows
  parse and contain valid executable step shapes.
- Actual Core/PostgreSQL/GPG process integration passes:
  `build/isolated-linux/update-transaction-report.json` and
  `build/isolated-linux/application-restore-report.json`. Core JAR SHA-256 is
  `b117623a942a9c8aa95f5b6dc95ec343896ef273a3cb14882c8db18ff196693a`.
  These replace lifecycle adapters, not encryption, database, migrations or Core.
  They do not certify SCM, Docker services or cold boot.
- Actual Windows portable GnuPG archive roundtrip, wrong-password rejection,
  134-character plaintext data parent and agent cleanup pass. Maximum agent-home
  length is 73 bytes. Evidence:
  `build/gpg-path-c8a3e273ea4143a389aca8d3fdc7ce74/report.json`.
  Administrator/parent policy is explicitly injected for this non-elevated local
  test. Real elevated system-folder ACL execution is prepared in Windows CI but
  has not run. Read-only real ProgramFiles preflight reaches the expected
  `E_NATIVE_ELEVATION`, without creating a directory.
- Native `.20261114.15` packages pass executable/resource smoke and exact raw
  source/artifact hash matching. Windows: 12,753,262 bytes, SHA-256
  `a4843692c593ab9cc3c065a13932ef79b13b8bfae6b3a780851ba7210ef89216`.
  Linux AMD64 archive: 14,559,461 bytes, SHA-256
  `c91cd771688c682ebbb0af451d5069e0b0e4f409a29f94500c3c3886f32bea24`.
  Artifacts/metadata reside under `build/native-installer/`, unsigned,
  unpublished and explicitly `platformInstallationAccepted: false`.
  Historical development 13 failed the deep-home integration; development 14
  still chose the incompatible ProgramData parent. Neither is accepted.

Native standalone backup database verification, same-root disaster restore,
unknown-source activation, distributed operation, managed optional AI/Voice and
the other ledger gaps remain source work. Productive signing/feed custody and
target-platform acceptance remain separate external requirements. This is an
internal continuation checkpoint, not a request for user acceptance.

# Debian Compose transaction continuation

The complete installer scope remains open in the [requirement ledger](../installer-requirements.md).
This checkpoint does not request partial user acceptance.

## Implemented correction

Actual Debian Compose 2.26.1-4 rejects `docker compose run --pull never`.
Update and restore administrative helpers now use a managed service override with
`pull_policy: never` and a validated immutable local `sha256:` image ID. They
retain `--no-deps`, read-only secret mounts and the existing Core administrative
entry point. Missing or mutable restore image identities fail before execution;
there is no fallback to a mutable release tag or registry download.
The separate supported `docker run` and `compose up` pull flags remain intact.

The systemd integration fixture now enters its explicit persistent test network
namespace. Private fixture credentials survive an interrupted test in a root-only
0600 file, excluded from public reports and release inputs. This is test-only
state, not an installer credential export feature.

## Verification

- Windows installer suite: 471 tests, nine skips, recorded in
  `build/installer-tests-20261114-compose-compatibility.txt`.
- Isolated Linux suite: 479 tests, twenty skips, recorded in
  `build/isolated-linux/test-report-current.txt`. New helper tests reject mutable
  image references and verify local-only Compose policies. Docker invocation is
  injected in these unit tests; the following transaction evidence is real.
- Changed Python lint passes. Native development version
  `0.0.0-dev.20261114.19` passes executable/resource smoke and exact source hash
  checks. Windows EXE: 12,771,641 bytes, SHA-256
  `067cac4a17a583a2a14333d755092e40b348cf94195d71d2515dd688ae2f3e05`.
  Linux AMD64 archive: 14,575,968 bytes, SHA-256
  `4b9a63d84c2e5981caff956594c37b39a397dc6f24bf23e99e565846dfebffa7`.
  Both remain unsigned, unpublished and `platformInstallationAccepted: false`.
- Actual Debian 13 AMD64 guest: systemd 257.13, Docker 26.1.5+dfsg1 and
  Compose 2.26.1-4. Fresh/repeated installation and TLS application readiness
  pass. Real native worker registration and systemd application startup pass.
  A signed synthetic release drives actual encrypted backup, database snapshot,
  migration 49 to 50, deliberately interrupted activation, systemd startup
  deferral while fenced, resumed activation and application health.
- Recovery restores schema 49 from the pre-update database snapshot rather than
  attempting a schema downgrade. Original identity and knowledge bytes match;
  local login succeeds after recovery. Evidence:
  `build/isolated-linux/systemd-update-final-continuation.txt` and the owned
  guest fixture's `continuation-report.json`.

The full transaction required separate continuations: initial PostgreSQL
recreation during switching and recovery returned `E_UPDATE_DOCKER`; repeat
execution succeeded. The initial raw Docker cause was not retained and is not
claimed resolved. The test's failure cleanup had removed its platform unit;
continuation restored the exact hash-checked owned unit and fixture namespace
drop-in before exercising the real frozen worker. No readiness or systemd probe
was replaced. An earlier fixture DNS failure was traced to WSL regenerating its
hosts file and corrected solely inside the disposable guest. WSL session
lifetime is held by an explicit bounded developer process during checks.

This is split transaction and real service-start evidence, not a single clean
uninterrupted full test, cold host boot, Windows SCM acceptance, ARM64 acceptance,
productive release or browser SSO acceptance. The repeated first recreation
failure still needs a captured reproduction. Existing data, encrypted backups
and test image references are preserved for diagnosis.

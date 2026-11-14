# ADR 0071: Consented Linux cryptography prerequisite

Status: Accepted for implementation, 2026-11-14.

The existing Linux backup format needs GnuPG. Windows includes a separately
verified portable dependency; do not create a second cryptography format.
For Debian 13, offer explicitly reviewed installation of the distribution's
`gnupg` package through APT. Other OS variants keep their concrete prerequisite
error until a supported package path exists. No shell installer, repository/key
addition, signature bypass, package removal or OS-wide upgrade is authorized.

The administrator first consents to refreshing existing package metadata. Parse
APT's simulated transaction, refusing removals, existing-package upgrades and
unrelated incomplete package work. Review exact package names/versions before
installation. Preserve the plan and progress in the existing protected installer
journal, pin versions during download/install and revalidate the plan before
mutation. Never display raw repository output, which can include credentials.
APT authentication remains enabled. Interrupted operations retain their intent;
only explicitly planned unfinished packages may be configured during recovery.
Do not run a global package-repair command.

This is an interactive prerequisite action, never an implicit action by a
scheduled backup/update worker. Root/host/file/authority checks and the existing
installation lock still apply. Success requires actual executable probes, not
an APT exit code alone. Package-manager simulation tests and clean-system package
acceptance must be reported separately.

Official reference checked 2026-11-14:
[Debian gnupg](https://packages.debian.org/trixie/gnupg) and
[Debian apt-get manual](https://manpages.debian.org/trixie/apt/apt-get.8.en.html).

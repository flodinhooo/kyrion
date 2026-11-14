# ADR 0072: Consented Debian runtime bootstrap in the existing journal

Status: Accepted for implementation, 2026-11-14.

The downloaded Linux installer currently requires an already installed Docker
Engine/Compose system service. That is an implementation gap, separate from the
remaining full-host acceptance. Reuse Debian 13's packaged `docker.io`,
`docker-cli`, `docker-compose`, GnuPG and CA certificates, the signed runtime archives, existing Compose
provisioning, systemd supervisor and protected installation journal. Windows
keeps its implemented native services, without Docker Desktop or WSL boot claims.

Extract the already tested APT transaction from the crypto-specific wrapper into
a cohesive shared package operation; do not introduce another installer state
database or shell-download runtime. Keep existing crypto journal compatibility,
reviewed exact versions, no-removal/no-existing-upgrade policy, protected output,
explicit confirmation and bounded recovery to its own unfinished packages.
Existing foreign Docker configuration/data and runtimes must be detected and
preserved; healthy compatible local engines can be consciously reused.

After authenticated release review and INSTALL confirmation, the Linux guided
path may create the existing journal in `reviewed` state before approved OS
packages are installed. This is deliberately different from adopting an
unowned pre-existing directory. Resume validates the exact configuration/release
and root binding. A journal-only/partially configured reviewed target still gets
fresh port and existing-container checks; directory existence alone must not
silently downgrade these checks. No application containers exist merely because
an OS-prerequisite journal exists. Source provisioning remains available for
prepared developer/operator hosts.

Review package downloads/allocation and any Docker system-service start/enable
separately. Validate real local rootful engine, Compose v2 and system-service
state afterwards. Do not modify daemon configuration, open TCP listeners, add
users to Docker groups or remove shared runtimes during Kyrion uninstall.
Current readiness, configured startup and actual cold boot remain distinct.
Unsupported/custom missing-runtime combinations get concrete limitations rather
than a simulated success or replacement of foreign software.

Debian package provenance references checked 2026-11-14:
[docker.io](https://packages.debian.org/trixie/docker.io),
[Compose v2](https://packages.debian.org/trixie/docker-compose),
[GnuPG](https://packages.debian.org/trixie/gnupg), and
[APT](https://manpages.debian.org/trixie/apt/apt-get.8.en.html).
Source implementation, real package tests, systemd execution, full application
installation and physical/ARM boot acceptance retain separate matrix evidence.

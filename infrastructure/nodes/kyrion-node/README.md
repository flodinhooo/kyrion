# kyrion-node Deployment

This directory contains deployment configuration for the physical Raspberry Pi
node named `kyrion-node`.

Device-specific addresses, credentials, SSH keys, radio network keys, Matter
fabrics, and voice recordings must not be committed. Checked-in configuration
must use placeholders and stable hardware identities such as
`/dev/serial/by-id` rather than transient `/dev/ttyUSB*` paths.

The development node currently runs the hardened gateway agent, Mosquitto and
Zigbee2MQTT. Applying updated service files still requires an explicit
privileged installation on the node; copying source to a temporary user-owned
path alone does not change the running service.

## Always-on Kyrion platform

For an existing installation, use the read-only `check-platform-update.ps1`
preflight and the [September update handoff](../../../docs/status/2026-09-05-web-pre-image-review.md).
The first-migration installer below must not be reused to update an existing
database or replace the Pi's environment and keys.

`compose.platform.yml` packages PostgreSQL, Kyrion Core and Kyrion Web as the
always-on control plane described by ADR 0016. Core and Web run as unprivileged,
capability-free containers with read-only root filesystems. PostgreSQL data and
the two Core key files remain in explicit host paths below `/var/lib/kyrion`.

Only HTTPS port `443` is exposed to the LAN. Web port `3000` and Core port
`18080` are published on loopback for local diagnostics and native gateway or
voice services; OTBR keeps its existing loopback port `8080`. PostgreSQL is not
published on the host. An unreachable AI URL does not prevent Core, Web or
bounded device control from starting.

Caddy terminates HTTPS with a self-signed server certificate constrained to
`kyrion-node.local` and the reserved Ethernet address. It is explicitly marked
`CA:FALSE`, so trusting it does not create a general certificate authority.
The private key remains under `/etc/kyrion/platform/tls` on the Pi and is never
exported. `enable-platform-https.sh` exports only the public server certificate
to the invoking administrator's home directory. Each client trusts that one
certificate before using `https://kyrion-node.local/`. Session cookies remain
Secure and HttpOnly with SameSite Lax for the Spotify OAuth callback; the
separate CSRF cookie remains SameSite Strict. The pinned certificate must be renewed
and redistributed before its documented 397-day validity ends.

The first migration is deliberately split into preparation and a visible
privileged activation:

1. On the Windows development host, run
   `prepare-platform-bundle.ps1`. It builds ARM64 images, creates a PostgreSQL
   custom-format dump and copies the existing credential and audit keys into a
   timestamped directory below `E:\Kyrion\Data\deployments`.
2. Copy that directory and `install-platform.sh` to a private owner-controlled
   staging directory on the Pi. The bundle contains secrets and must never be
   committed or placed in a generally readable directory.
3. On the Pi, run `sudo ./install-container-runtime.sh` once to install both
   Docker and Docker Compose, then run
   `sudo ./install-platform.sh /path/to/private/bundle`.
4. Enable HTTPS, trust the exported public root certificate on the client and
   verify Web on `https://kyrion-node.local/`. Switch one lamp through the
   shared Core command path, turn off the development PC and repeat.
5. After verification, remove the private staging bundle. Retain a protected,
   tested backup of the database and both key files elsewhere.

The installer refuses occupied platform ports, an existing PostgreSQL data
directory or missing migration artifacts. It starts and restores PostgreSQL,
waits for Core and Web health, and only then changes the gateway agent from the
development PC to `http://127.0.0.1:18080`. The prior agent configuration is
kept under `/var/backups/kyrion` for explicit rollback.

`install-container-runtime.sh` installs Debian's maintained Docker Engine
package for separately scoped Home Assistant, OTBR, and Matter services. It
does not add the interactive owner or the gateway agent to the `docker` group,
because Docker socket access is equivalent to root authority. It also does not
flash a radio or create a Thread or Matter network.

`install-home-assistant.sh` starts Home Assistant Container with host networking
for local discovery but without privileged mode, Linux capabilities, the Docker
socket, D-Bus, or radio access. Its persistent configuration is kept under
`/var/lib/homeassistant`. OTBR and Matter remain separate services.

`prepare-zbt2-thread-firmware.sh` creates a root-only, checksum-verified restore
set for the accepted ZBT-2. `flash-zbt2-thread.sh` switches that adapter from
Zigbee NCP to OpenThread RCP and verifies the resulting Spinel version.

`install-otbr.sh` enables the documented forwarding settings for the wired
infrastructure interface and starts the official OTBR image by immutable image
digest. The container receives only `NET_ADMIN`, `NET_RAW`, `/dev/net/tun`, and
the accepted ZBT-2 serial device. `NET_RAW` is required for IPv6 Multicast
Listener Discovery. Persistent Thread state is kept under `/var/lib/otbr`.

`install-matter-server.sh` starts the official matter.js Matter Server as an
unprivileged, capability-free container. Its WebSocket API listens only on
loopback for the colocated Home Assistant container, while host networking and
the wired primary interface provide Matter IPv6 and mDNS connectivity. Matter
fabric state is stored under `/var/lib/matter-server`.

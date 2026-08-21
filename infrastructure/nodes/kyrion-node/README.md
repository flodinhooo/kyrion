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

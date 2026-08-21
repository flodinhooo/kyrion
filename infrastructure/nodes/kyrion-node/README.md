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

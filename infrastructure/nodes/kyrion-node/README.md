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

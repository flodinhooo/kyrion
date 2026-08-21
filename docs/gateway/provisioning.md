# Gateway Provisioning

## Current node

- Hostname: `kyrion-node`
- Local DNS name: `kyrion-node.local`
- Reserved Ethernet IPv4 address: `192.168.1.116`
- Reserved Wi-Fi IPv4 address: `192.168.1.115`
- SSH user: `flodinho`
- Operating system: Debian GNU/Linux 13 (`trixie`), ARM64
- Kernel: `6.18.39+rpt-rpi-2712`
- Deployment state: Kyrion gateway agent, native Zigbee2MQTT and Mosquitto
  services are active; Home Assistant is not installed

The address is operational metadata, not a public contract. Later gateway
registration must use a stable cryptographic node identity rather than an IP
address or hostname as authority.

## Provisioning sequence

1. Complete a read-only operating-system and hardware inventory. Completed on
   2026-08-06.
2. Record storage health, power state, temperature, networking, IPv6, mDNS,
   Bluetooth, USB, and audio devices.
3. Decide the host deployment model before installing Home Assistant or radio
   services.
4. Define Core-owned node registration, credential rotation, heartbeat, health,
   restart, temporary-network-loss, update, and recovery contracts.
5. Establish configuration backup and verified recovery before material radio
   or device onboarding.
6. Attach and identify each radio separately using stable USB identities.
7. Validate Zigbee, Thread/OTBR, Matter, Bluetooth, and voice independently.

Secrets, private SSH keys, passwords, radio network credentials, Matter fabric
credentials, and captured audio must never be committed.

## SSH status

On 2026-08-06 a dedicated Ed25519 management key was authorised and verified
without a password. The key grants only the permissions of the `flodinho`
account; non-interactive `sudo` is not enabled.

## Deployment model

ADR 0007 keeps Debian as the host. The gateway agent will run as an
unprivileged native system service. Mature protocol components may run as
separately scoped containers, and Home Assistant remains an optional adapter.

Provisioning is a visible administrator operation. The runtime agent must not
receive unrestricted `sudo`, access to the Docker socket, or a general shell
execution API. Hardware and service permissions are added only with the
vertical slice that requires them.

## Implemented runtime

The `0.1.0` gateway agent is installed under `/opt/kyrion-gateway` and runs as
the dedicated `kyrion-gateway` system identity. Its protected configuration is
stored at `/etc/kyrion-gateway/agent.json`. The service is enabled as
`kyrion-gateway-agent.service`, sends a heartbeat every 5 seconds and polls the
Core-owned typed command queue over the same outbound authenticated channel.

Zigbee2MQTT 2.10.1 is installed under `/opt/zigbee2mqtt`, keeps runtime data in
`/var/lib/zigbee2mqtt` and runs as `zigbee2mqtt.service`. Mosquitto runs as a
separate service bound only to `127.0.0.1:1883`; the Zigbee2MQTT frontend is
disabled. The Sonoff coordinator uses its stable `/dev/serial/by-id` identity,
the Ember driver, firmware 7.4.4 and channel 15. Root-only pre-pairing and
post-Hue-pairing snapshots are under `/var/backups/kyrion/zigbee`.

Kyrion Core is reached through the router-provided local DNS name
`kyrion-core.home`, currently as `http://kyrion-core.home:8080`. Gateway and
Voice Satellite configuration must use that name instead of a numeric Core
address. This avoids configuration changes when DHCP assigns the Core host a
different address while keeping discovery explicit and auditable. It is local
DNS, not public DNS or automatic trust: node credentials still authenticate
every request, and a Windows firewall rule permits Core port 8080 only from the
Pi's reserved `192.168.1.115` Wi-Fi and `192.168.1.116` Ethernet addresses.

The router entry must remain named `kyrion-core`, and the Pi must resolve
`kyrion-core.home` before either runtime is reconfigured. If router DNS is
unavailable, restore the previous protected configuration rather than falling
back to network scanning or accepting an unverified Core.

## Deferred owner onboarding

This document describes the current development provisioning flow. It is not a
finished installation experience for non-technical owners. Kyrion will first
validate the planned radio, device and voice integrations on this node. Once
those contracts and operational requirements are known, the flow will be
replaced by guided German/English onboarding, packaged installation and update
support, automatic local discovery, safe permission setup and understandable
diagnostics.

The final acceptance test will reset this Raspberry Pi and onboard it again as
if it were a new owner's device. Product readiness requires completing that
test without SSH, manual firewall editing, programming knowledge or copied
terminal commands.

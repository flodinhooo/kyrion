# Gateway Provisioning

## Current node

- Hostname: `kyrion-node`
- Local DNS name: `kyrion-node.local`
- Reserved Ethernet IPv4 address: `192.168.1.116`
- Reserved Wi-Fi IPv4 address: `192.168.1.115`
- SSH user: `flodinho`
- Operating system: Debian GNU/Linux 13 (`trixie`), ARM64
- Kernel: `6.18.39+rpt-rpi-2712`
- Deployment state: Kyrion gateway agent registered and active; protocol
  containers and Home Assistant are not installed

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
`kyrion-gateway-agent.service` and sends a heartbeat every 15 seconds.

Kyrion Core currently runs at `192.168.1.107:8080`. A Windows firewall rule
permits that port only from the Pi's reserved `192.168.1.115` Wi-Fi and
`192.168.1.116` Ethernet addresses. These development addresses are deployment
metadata, not gateway identity.

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

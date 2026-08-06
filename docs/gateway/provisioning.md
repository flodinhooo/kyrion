# Gateway Provisioning

## Current node

- Hostname: `kyrion-node`
- Local DNS name: `kyrion-node.local`
- Reserved Ethernet IPv4 address: `192.168.1.116`
- SSH user: `flodinho`
- Operating system: Debian GNU/Linux 13 (`trixie`), ARM64
- Kernel: `6.18.39+rpt-rpi-2712`
- Deployment state: operating system prepared; Kyrion, containers, and Home
  Assistant are not installed

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

# ADR 0007: Debian Gateway Host and Least-Privilege Runtime

- Status: Accepted
- Date: 2026-08-06

## Context

The first physical gateway is a Raspberry Pi 5 with 8 GB RAM and a 64 GB
microSD card. It arrived with a current Debian 13 ARM64 installation, working
Ethernet, IPv6, Bluetooth, SSH, and Raspberry Pi health tooling. Replacing the
host with Home Assistant OS would discard the prepared installation and bind
Kyrion's gateway lifecycle to the Home Assistant add-on model.

Kyrion needs mature Zigbee, Thread, Matter, Bluetooth, and optional Home
Assistant connectivity without allowing Web, the AI service, protocol
containers, or the gateway agent to obtain unrestricted host authority.

## Decision

The first `kyrion-node` keeps Debian as its host operating system.

- The Kyrion gateway agent runs as a dedicated native system service and uses
  a dedicated unprivileged service identity.
- Mature protocol components run as separately scoped containers where their
  networking and hardware requirements are compatible with reliable operation.
- Home Assistant may run as an optional bounded adapter. It does not become the
  node identity, Kyrion authority, or the direct Web/AI execution boundary.
- Zigbee and Thread use separate physical radios and separate services.
- Host provisioning remains an explicit administrator action. Neither the SSH
  management key nor the gateway service receives unrestricted passwordless
  `sudo`.
- The runtime service receives only the device groups, files, sockets, network
  access, and narrowly defined service operations required by an implemented
  vertical slice.
- Core registration credentials, radio network credentials, Matter fabric
  material, and Home Assistant credentials remain outside Git and are readable
  only by their owning service.

The initial deployment may use Docker Compose for local protocol components,
but checked-in Compose files are deployment descriptions rather than Core's
authority. Exposing a Docker socket to the gateway agent is prohibited because
it is equivalent to host root access.

## Consequences

- The existing host installation and normal Debian administration remain
  usable.
- Kyrion can manage its own agent lifecycle without becoming a Home Assistant
  add-on.
- Home Assistant Container does not provide the Home Assistant OS add-on store;
  required protocol services must be deployed and backed up explicitly.
- Thread/OTBR and Matter networking require dedicated IPv6 and multicast
  validation before they are accepted.
- Provisioning requires occasional visible owner-approved administrator steps.
- Each new hardware or service capability must justify any additional runtime
  permission.

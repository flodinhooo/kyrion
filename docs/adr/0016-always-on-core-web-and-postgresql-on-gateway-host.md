# ADR 0016: Always-on Core, Web and PostgreSQL on the Gateway Host

- Status: Accepted
- Date: 2026-08-28

## Context

The physically verified Zigbee and Bluetooth light paths depend on Kyrion Core
running on the development PC. When that PC is off, the Raspberry Pi retains
radio connectivity but cannot receive Core-authorised commands. Permanent light
control is a concrete local-first use case and does not require language-model,
speech or other AI capabilities.

The Raspberry Pi 5 has 8 GB RAM, sufficient persistent storage and an existing
least-privilege Debian container runtime. It already hosts the outbound-only
gateway agent, Zigbee2MQTT, Mosquitto and protocol containers. OTBR owns
loopback port 8080. The gateway host must remain an integration boundary even
when Core is colocated with it.

## Decision

The first always-on deployment places PostgreSQL, Kyrion Core and Kyrion Web in
separate ARM64 containers on `kyrion-node`.

- Core remains the sole authority for authentication, permissions, command
  validation, persistence and correlated audit.
- The native gateway agent continues to execute only bounded typed operations.
  Colocation does not grant it database, Core-secret or Docker-socket access.
- Web communicates with Core on a private container network and exposes only
  port 3000 to the local network.
- Core publishes port 18080 only on host loopback for the native gateway and
  voice services. OTBR retains port 8080.
- PostgreSQL has no host-published port. Its data uses an explicit persistent
  host path.
- Credential and audit-integrity keys are migrated with the database, stored
  outside the images and readable only by the Core runtime identity.
- The AI service remains optional on the development PC. An unreachable AI
  endpoint produces an explicit unavailable result for AI-dependent flows but
  does not disable Web, Core or deterministic device commands.
- Containers restart unless stopped, run without additional Linux
  capabilities and use read-only root filesystems where their runtime permits.
- Initial activation remains a visible administrator operation. Neither the
  gateway agent nor Web receives Docker or host-service lifecycle authority.

## Consequences

Lamp control and other implemented deterministic Core actions can remain
available while the development PC and AI runtimes are off. The Web interface
also becomes independent of the PC.

The Pi becomes the authoritative location of the live database and Core key
material. Backups must therefore cover PostgreSQL and both keys together, and a
return to the PC requires an explicit reverse migration rather than running two
authoritative Core instances against diverging databases.

Nanoleaf multicast discovery may require separate validation through the
container network. Existing, directly addressed Nanoleaf connections and
gateway-queued Zigbee/Bluetooth commands do not depend on that discovery path.

AI becomes a visibly degradable remote capability. Enabling it from the Pi
requires an explicit LAN bind and a firewall rule restricted to the Pi; it must
not be exposed generally to the local network or internet.

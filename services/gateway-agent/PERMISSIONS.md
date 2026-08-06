# Gateway Agent Permissions

## Initial health slice

The gateway agent runs under a dedicated system identity with:

- no interactive login shell;
- no password;
- no `sudo` access;
- no Docker socket access;
- read access only to the operating-system metrics required by the typed health
  contract;
- outbound network access only for authenticated communication with Kyrion
  Core and explicitly configured local adapters.

Creating the service identity is deferred until the first executable agent and
its systemd unit exist, so ownership and filesystem permissions can be verified
together rather than leaving an unused privileged identity behind.

## Capability-specific additions

Permissions are added only with a verified vertical slice:

- Zigbee or Thread serial access: the exact stable USB device and `dialout` if
  the selected protocol service requires it;
- voice capture and playback: `audio` plus access to the selected stable audio
  devices;
- Bluetooth: a bounded D-Bus policy or dedicated helper interface rather than
  unrestricted system-bus access;
- service lifecycle: narrowly named root-owned systemd operations invoked by a
  separately authorised administrative path, never general command execution.

Protocol containers receive only their own radio device and required network
mode. The gateway agent does not receive membership of the `docker` group,
because access to the Docker daemon is equivalent to host root authority.

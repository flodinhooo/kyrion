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

The executable and reference systemd unit now exist. Host provisioning must create
and verify the dedicated identity and exact filesystem permissions together.
The original deferred-slice wording was historical; it did not describe the
existing reference runtime. General downloaded-installer node deployment remains
unfinished. Prepared enrollment runs as the agent identity, owns only its private
configuration/pending credentials, uses checked local TLS and receives no Docker
or general administrative authority. A source change does not provision accounts
or alter existing deployed units.

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

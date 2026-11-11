# ADR 0047: selected Home Assistant inventory and bounded control

Status: accepted for implementation, 2026-11-11. This extends ADR 0018 following
the owner's explicit full installer requirements. It does not grant HA authority
to the installer, Web, AI or arbitrary plugin code.

Core retains the existing encrypted HA connection, owner/Space boundary, import
identity and refresh scheduler. Add owner-scoped persisted inventory selections
with optimistic revisions and explicit room overrides. Existing installations
without a selection remain read-only with their existing import semantics. An
explicit empty selection imports nothing. Selection never performs a device action.

The setup preview exposes opaque source/entity keys, names, observed state and
supported capabilities. Provider registry/entity IDs stay inside Core. Selection
keys must resolve against a freshly read inventory for the authenticated owner;
room IDs must belong to the same Space. Replacement is transactional under the
existing owner row lock and immediately reconciles the catalog. A room override
survives future provider snapshots. Unselected/removed entries lose control.

The first supported HA command is `power.set` for an explicitly selected single
light/switch entity with explicit control consent. DeviceCommandService remains
the common entrypoint, including existing authority, membership, permission,
capability, target and correlated audit checks. The adapter resolves the selected
entity, rechecks live inventory/availability and calls only fixed light/switch
turn_on/turn_off services. A fresh state read must confirm the requested value;
HTTP 200 alone is not confirmation of a physical effect. Unsupported brightness,
colour, scripts, scenes and arbitrary HA services remain unadvertised.

Tests use synthetic snapshots and isolated HA-compatible endpoints. No household
devices are switched. Physical HA/controller/device acceptance is a separate gate.
Deduplication across providers requires an explicit human resolution; no heuristic
identity merge is introduced by this slice.

Official [HA REST API](https://developers.home-assistant.io/docs/api/rest/) was
checked on 2026-11-11. State writes to `/api/states` do not control devices and
must not be used as a substitute for a service call and subsequent state read.

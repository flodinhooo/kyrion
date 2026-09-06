# Home Assistant device snapshot import

Status: implemented; automated and physical verification are reported separately
in the [consolidation report](status/2026-09-06-platform-consolidation.md).

Home Assistant supplies inventory and observations. Core owns identity, owner
scope, room assignment, persistence, audit and the public device catalog.
This is not a full Home Assistant integration or a native Shelly integration.

## Configuration and use

Set these variables only in the Core process environment (or the platform
Compose environment), following `infrastructure/.env.example`:

- `KYRION_HA_URL`: the HA base URL, for example `http://192.168.1.20:8123`;
- `KYRION_HA_TOKEN`: an owner-controlled HA access token, kept out of Git and Web;
- `KYRION_HA_OWNER_ID`: the authenticated Kyrion owner's UUID (`GET /v1/auth/me`).

Empty configuration disables the import. This minimal slice accepts literal
private IPv4 addresses, HTTP or HTTPS, no URL credentials, path, query or fragment,
and follows no redirects. DNS names, multiple HA installations per owner and
credential editing in Web are intentionally deferred. Use one HA installation
per owner; do not repoint it to a different installation without reviewing the
existing imported inventory. Core must be restarted after environment changes.

In **Settings > System services**, the Home Assistant card shows configuration
and the last sync diagnostic. **Import / sync devices** explicitly reads HA and
updates the catalog. Devices appear under Devices and Home using Kyrion IDs.
The request requires a Kyrion owner session and Web CSRF protection. The server
also exposes `POST /v1/integrations/home-assistant/sync` and a read-only status
at `GET /v1/integrations/home-assistant`.

The token may grant broader authority within HA; Kyrion exposes no arbitrary
template, service or control endpoint. The only provider request is a fixed
read-only template at `/api/template`.

## Mapping and reconciliation

- Registry-backed devices with `sensor`, `binary_sensor`, `light` or `switch`
  state entities are imported. Entity-only helpers and devices with no such
  states are outside this bounded inventory. Up to 250 devices / 2000 state
  rows / 2 MB are accepted; oversized snapshots fail without partial import.
- Provider plus HA device registry ID is unique within the Kyrion owner.
  Repeated syncs update the same connection UUID, name, device class, hardware
  label, room and observations. Entity identifiers never enter public views.
- HA device-area names are trimmed and compared case-insensitively using a
  locale-independent comparison. Only one exact existing owner-room match is
  accepted. Missing areas, missing rooms and ambiguous matches map to `null`,
  displayed as **Nicht zugeordnet / Unassigned**. No room is created. No Voice
  room synonyms, punctuation removal, substring matching or fuzzy matching apply.
- Sync intentionally replaces imported names and room assignments with the HA
  mapping, including clearing an earlier assignment. Removing an imported device
  locally does not remove it from HA; the next import can recreate it.
- Supported observations: power, temperature (Celsius, converting Fahrenheit),
  relative humidity, battery and occupancy/motion/presence. Read capabilities
  remain declared while an entity is unavailable. Conflicting multiple numeric
  sensors are not silently selected; their value is omitted and health degraded.
- HA timestamps describe provider observations, not independently verified
  physical measurements. A device-level timestamp conservatively uses the oldest
  included entity update. Missing readings stay null, never zero.
- All HA devices are read-only, including lights. They never advertise
  `power.set`, `light.setBrightness` or `light.setColour`.
- All-unavailable states report offline; mixed valid/unavailable data reports
  degraded; all unknown/unavailable without an explicit all-unavailable result
  reports unknown. Missing devices in a later snapshot remain cataloged as
  unknown. A failed HA connection preserves prior device readings; it does not
  assert that all physical devices are offline. Catalog availability expires
  after the existing 60-second observation window.

## Scope

Implemented: operator connection/configuration, explicit device import, bounded
basic state/sensor import, mapping to existing rooms, stable reconciliation,
owner boundaries, status diagnostics and correlated sync audit.

Not implemented: control, services, automations, scenes, dashboards, HA users,
event ingestion, webhooks, event bus, MQTT forwarding, permission profiles,
backup/restore integration or automation migration. No native Shelly acceptance
is implied by importing a Shelly device through HA.

## Verification still required

Use a real HA installation and Shelly/sensor hardware to check token access,
registry identities, area labels, Celsius/Fahrenheit units, rename, room change,
offline transitions and repeated sync. Automated fixtures do not verify the
template against a live HA version or the downstream hardware.

References: [HA REST API](https://developers.home-assistant.io/docs/api/rest/),
[HA template functions](https://www.home-assistant.io/template-functions/),
[ADR 0018](adr/0018-read-only-home-assistant-import.md).

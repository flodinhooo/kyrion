# Nanoleaf Integration

## Status

The first official internal integration is implemented against Nanoleaf's
local OpenAPI. It is not a Nanoleaf cloud-account integration and does not use
undocumented vendor endpoints.

## Ownership and authorisation

Each Kyrion owner authorises each controller separately. Kyrion discovers
controllers through `_nanoleafapi._tcp.local` mDNS advertisements. Discovery
does not grant control: the owner must open the controller's API-authorisation
window and explicitly allow Kyrion to request its own token.

Core stores connection metadata in PostgreSQL. Tokens are encrypted with
AES-256-GCM and are never returned to the browser. The installation key is
stored separately at `E:/Kyrion/Data/secrets/credential.key` by default and can
be relocated with `KYRION_CREDENTIAL_KEY_FILE`. Losing that key requires
authorising the affected controllers again.

## Implemented capabilities

- automatic local discovery with manual IPv4 fallback;
- persistent owner-specific connections and editable display names;
- current power, brightness, hue, saturation, colour temperature and colour
  mode reads where supplied by the controller;
- power, brightness, colour and colour-temperature commands;
- stored scene/effect listing, active-scene reads and scene activation;
- real scene-palette previews when effect definitions expose HSB or hex
  palettes;
- persistent owner-specific rooms and device assignments;
- live dashboard status, quick power actions and detailed device controls;
- confirmation for connection removal;
- Core validation and activity events for important commands.

## Persistence model

Flyway V8 creates `integration_connection`; V9 creates `owner_room` and adds
the optional room assignment. Connections survive Web, Core and host restarts.
Deleting a room does not delete integrations: its devices become unassigned.
Deleting a connection removes the Kyrion credential record and requires a new
controller authorisation before Kyrion can control it again.

## Current limitations and follow-up

- Controller IP addresses are persisted. Discovery finds current addresses,
  but automatic reconciliation after a DHCP address change is not implemented.
- Dashboard status is fetched when the page loads; background refresh and
  event-driven updates are not implemented.
- Some custom scenes do not expose a palette and therefore use a neutral
  preview.
- Provider-neutral device/capability contracts are not yet stable; current Web
  control routes remain Nanoleaf-specific.
- Token revocation on the physical controller during Kyrion connection removal
  should be added where the controller is reachable.
- The local API requires Kyrion and the controller to share a network that
  permits mDNS and TCP port 16021.

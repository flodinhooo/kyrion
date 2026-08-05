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
- visible bounded status refresh with provider-neutral availability and the last
  real observation time;
- Home quick-power actions executed through the provider-neutral Core command
  path using an exact owner-scoped device identifier;
- confirmation for connection removal;
- Core validation and activity events for important commands.
- bounded German and English Velora commands for room-scoped power and
  brightness changes, with Core-confirmed results returned to text and
  browser-backed voice conversations.
- exact unique catalog-name targeting for one device, translated into a stable
  owner-scoped device ID before Core execution; partial and duplicate names are
  refused.
- an owner-scoped provider-neutral runtime catalog exposing device identity,
  room and supported capability identifiers without hosts or credentials.

## Persistence model

Flyway V8 creates `integration_connection`; V9 creates `owner_room` and adds
the optional room assignment; V10 persists the latest bounded device
observation. Connections and observations survive Web, Core and host restarts.
Deleting a room does not delete integrations: its devices become unassigned.
Deleting a connection removes the Kyrion credential record and requires a new
controller authorisation before Kyrion can control it again.

## Current limitations and follow-up

- Controller IP addresses are persisted. Discovery finds current addresses,
  but automatic reconciliation after a DHCP address change is not implemented.
- Dashboard catalog reads are passive. A visible protected manual bounded
  observation refresh updates availability, but background refresh and
  event-driven updates are not implemented.
- Some custom scenes do not expose a palette and therefore use a neutral
  preview.
- Provider-neutral device/capability contracts are not yet stable; current Web
  control routes remain Nanoleaf-specific.
- Token revocation on the physical controller during Kyrion connection removal
  should be added where the controller is reachable.
- The local API requires Kyrion and the controller to share a network that
  permits mDNS and TCP port 16021.
- Conversational device control currently recognises only explicit imperative
  Nanoleaf power and brightness commands using an exact room or exact unique
  device display name. Broader language interpretation, ambiguous-name
  clarification, colours, scenes and pronoun/context resolution remain
  follow-up work. The runtime capability catalog exists for official
  connections but its contracts are not yet stable or plugin-facing.

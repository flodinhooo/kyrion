# Nanoleaf and Home Dashboard Session — 2026-08-04

## Outcome

Kyrion's original Nanoleaf prototype goal now works as a Core-owned,
owner-specific vertical slice. Two physical Light Panel controllers were
discovered, authorised and persisted. The Home placeholder was replaced by a
persistent room dashboard with live controls.

## Integration and security

- Added an official internal Plugins catalog and Nanoleaf detail page.
- Confirmed that the public Nanoleaf developer interface is local OpenAPI, not
  a public third-party cloud OAuth API.
- Added mDNS discovery for `_nanoleafapi._tcp.local`; both local controllers
  were found automatically.
- Added physical API authorisation and separate tokens per Kyrion owner.
- Added Flyway V8 `integration_connection` persistence.
- Encrypted tokens with AES-256-GCM; the default installation key lives at
  `E:/Kyrion/Data/secrets/credential.key`, separately from PostgreSQL.
- Restricted manually entered controller targets to private/link-local IPv4.
- Kept all provider calls and credentials inside Core.
- Added confirmation and a modal warning before connection removal.

## Device capabilities

- Persistent editable controller names.
- Power state and confirmed on/off commands.
- Brightness reads and commands.
- Hue/saturation colour commands.
- Colour-temperature reads and commands from 1200 to 6500 K.
- Stored scene/effect listing and active-scene selection.
- `requestAll` effect metadata parsing and real palette previews from HSB or
  hex palettes where available.
- Integration activity events for pairing and important commands.

## Home dashboard

- Added Flyway V9 `owner_room` persistence and optional connection room IDs.
- Added owner-specific room creation, rename and confirmed deletion.
- Deleting a room leaves devices connected and unassigned.
- Added persistent device-to-room assignment.
- Replaced `/home` placeholder with grouped room and unassigned sections.
- Added automatic status reads, online/offline presentation and quick power
  controls on device cards.
- Added a device dialog with power, brightness, colour, colour temperature and
  scenes.
- Refined desktop/mobile layout and light/dark theme action hierarchy.
- Added green/red power actions with a visible power symbol.

## Runtime and verification

- Flyway migrations V8 and V9 applied successfully to local PostgreSQL.
- Core was restarted after each contract change and reported `UP`.
- Both integration records survived restarts.
- Core tests and Boot JAR passed after the final backend changes.
- Web tests, ESLint and Next.js production builds passed after final UI changes.

## Known follow-up

1. Define provider-neutral device-state and capability contracts above the
   Nanoleaf-specific routes.
2. Add bounded status polling or device event subscriptions.
3. Reconcile a persisted controller after its DHCP address changes.
4. Revoke the physical token when removing an online controller.
5. Add focused HTTP integration tests for room owner isolation and command
   validation.
6. Complete a systematic responsive German/English visual regression pass.
7. Add login throttling and verified backup/restore before remote exposure.

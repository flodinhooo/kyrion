# Spatial Home and Device Controls — 2026-08-19

## Outcome

- `/home` is now a spatial room overview instead of the detailed device-management screen.
- Rooms are selectable and reveal a compact device overview.
- Rooms can be created directly from the spatial Home view.
- Selecting a room opens a dialog with its devices; selecting a device opens its existing full control dialog without leaving Home.
- Unassigned devices can be dragged onto a room; the assignment still uses the existing Core-owned room API.
- Detailed status, controls, rename, removal, and room administration moved to `/devices`.
- The navigation exposes the new device-control page in German and English.
- Each room on `/devices` has one aggregate power switch. It turns the room off when any device is on and turns it on when all devices are off, reusing the existing validated device-command paths.
- Zigbee colour controls initialize from the device's observed hue and saturation instead of a fixed cyan placeholder.
- Manual status refresh is provider-neutral: Core delegates observation to registered provider observers. Nanoleaf performs a local state read and Zigbee/Hue derives availability and state from the current authenticated gateway heartbeat; future providers can join without changing the Web endpoint.

## Deliberate scope

The spatial view is a responsive CSS-based 2D/pseudo-3D floor plan. It does not yet persist exact room geometry or device coordinates. A true editable floor-plan model would require a dedicated, Core-owned layout contract and persistence model.

## Verification

- Web ESLint passed.
- All 20 Web tests passed.
- The Next.js production build passed and emitted `/home`, `/devices`, and `/devices/add`.

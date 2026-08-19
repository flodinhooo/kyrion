# Spatial Home and Device Controls — 2026-08-19

## Outcome

- `/home` is now a spatial room overview instead of the detailed device-management screen.
- Rooms are selectable and reveal a compact device overview.
- Unassigned devices can be dragged onto a room; the assignment still uses the existing Core-owned room API.
- Detailed status, controls, rename, removal, and room administration moved to `/devices`.
- The navigation exposes the new device-control page in German and English.
- Each room on `/devices` has aggregate on/off actions. These reuse the existing validated device-command paths rather than executing provider logic in the browser.

## Deliberate scope

The spatial view is a responsive CSS-based 2D/pseudo-3D floor plan. It does not yet persist exact room geometry or device coordinates. A true editable floor-plan model would require a dedicated, Core-owned layout contract and persistence model.

## Verification

- Web ESLint passed.
- All 20 Web tests passed.
- The Next.js production build passed and emitted `/home`, `/devices`, and `/devices/add`.

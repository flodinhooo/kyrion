# Bluetooth light Voice control — 2026-08-22

## Outcome

The deterministic German and English Voice proposal path now includes approved
Bluetooth lights. Spoken room commands such as `Schalte die Lampen im
Wohnzimmer an` target every light in the Core-resolved room, independent of
whether its provider is Bluetooth, Zigbee, Nanoleaf, Matter or a future
integration. Exact approved names such as `Schalte Lampe Rechts aus` use the
same provider-neutral light category; Core resolves the device ID to its real
provider only after validating ownership and capabilities.

Room-scoped brightness commands using `Lampe` or `Licht` are provider-neutral
as well. Nanoleaf-specific wording remains Nanoleaf-specific. Colour Voice
commands are not part of this bounded slice yet; Web colour control remains
available.

## Security and architecture

- AI receives only the owner-visible safe device catalog and proposes a typed
  command; it does not access Bluetooth.
- Core resolves rooms, checks the provider-neutral category, device identity and
  advertised capability, then applies the existing action policy and audit
  path.
- The gateway agent remains the only component that performs the bounded
  Bluetooth operation.

## Verification

- AI Ruff passed.
- All 110 AI tests passed, including Bluetooth room power, room brightness,
  exact-device power and a provider-agnostic future-light regression.
- The complete Core test suite passed.
- Physical Voice Satellite execution remains to be verified after restarting
  the local AI and Core services with this change.

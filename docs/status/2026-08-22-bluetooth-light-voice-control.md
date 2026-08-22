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
- At 16:36 CEST the German room-power path switched the physical living-room
  lights and returned `Erledigt`, but the owner rejected the observed order.
  Device execution occurred before `Alles klar, ich kümmere mich darum`. The
  required order remains: end of speech/VAD, processing response, device
  execution, truthful final result.
- Room brightness remains intentionally unverified until ambient light permits
  a reliable visual judgement.
- Exact-name power control remains to be physically verified independently.

## Explicit gratitude close

The complete German utterances `Danke Velora` and `Vielen Dank Velora` now
close the active Voice session and select one of five fixed responses. Plain
`Danke` and longer contextual sentences do not trigger this bounded intent.
The owner reviewed two Velora candidates per line and selected takes
`1, 2, 1, 2, 2`. Those five mono PCM16/24 kHz WAVs are checksum-pinned in the
production manifest. All five resolved from the restarted AI service as HTTP
200 RIFF/WAV responses. Physical Voice Satellite acceptance remains pending.

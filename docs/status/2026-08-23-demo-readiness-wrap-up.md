# Demo-readiness wrap-up — 2026-08-23

## Outcome

The work session produced a physically useful Voice and device-control slice
for the owner's demonstration. The owner confirmed that living-room light
commands through the Raspberry Pi Voice Satellite work again after the final
recognition and catalog-contract fixes. The intended action sequence is now
two-phase: Velora first plays the processing acknowledgement, Core then
executes the validated action, and the Satellite plays the truthful completion
response only after execution.

Approved Bluetooth lights participate in the provider-neutral `light`
category. Current and future integrations can therefore expose compatible
lights through the same Core-owned capability path without adding separate
phrases for each manufacturer.

## Voice fixes and evidence

- German and English room power and brightness parsing accepts `Licht`,
  `Lichter`, `Lampe` and `Lampen` for provider-neutral lights.
- Polite Web/Voice input such as `Kannst du die Lampen im Flur bitte
  ausschalten?` is recognised, including browser transcripts that insert a
  space before punctuation.
- The real Parakeet mistranscription `Schaute das Licht im Wohnzimmer aus`
  is treated as the bounded `Schalte ... aus` power intent.
- The AI device-proposal contract now accepts the complete safe catalog
  (`light`, `switch`, `sensor`, `other`). Adding the Zigbee button and motion
  sensor no longer makes every light proposal fail with HTTP 422.
- `Danke Velora` and `Vielen Dank Velora` close the session through one of five
  reviewed, checksum-pinned fixed responses. Plain `Danke` remains ordinary
  dialogue.
- The owner physically confirmed working living-room Voice light control after
  these corrections.

The final AI verification during diagnosis passed 114 tests and Ruff. The
complete Core test suite passed after the shared commanded-power-state change.

## Wireless button

The SONOFF SNZB-01P is approved and has three persisted room bindings:

- single click: toggle the two Bluetooth lights in `Wohnzimmer`;
- double click: toggle the two Zigbee lights in `Gang`;
- long press: toggle the Nanoleaf light in `Schlafzimmer`.

Gateway logs prove that `single`, `double` and `long` events reach Core through
the authenticated gateway endpoint. Double click is physically confirmed as
working reliably. Bluetooth OA20 devices report `on: null`, so the original
single-click toggle always calculated `on=true`. Core now keeps the last
successfully commanded power state shared across Voice, Web and automation
channels. The fixed JAR was started at 22:14 CEST and remained LAN-reachable
from the Pi. A final two-click physical acceptance after that exact restart was
not recorded before this wrap-up and remains the first retest.

Long press executes, but the owner observed noticeable latency. Do not optimise
it without measuring the separate hold-detection time, gateway/Core time and
Nanoleaf adapter time. This is a performance follow-up, not an unproven claim
that the binding is missing.

## System-service visibility

An authenticated `/settings/services` page now shows the local Web, Core, AI,
Ollama and Parakeet services plus Core-confirmed Raspberry Pi service health.
It exposes bounded status, host, port, latency and heartbeat metadata and
refreshes every five seconds.

The page distinguishes `ready`, `unavailable`, `degraded`, `unknown` and
`not_configured`. Home Assistant, Matter and Thread/OTBR are genuinely not
configured. MQTT and Zigbee are ready. Voice Satellite runs as a user service;
a bounded process observation was added to the gateway agent because its
hardened system identity cannot access the user's D-Bus session. The updated
gateway health module was staged as `/tmp/health.py`; installing it under
`/opt/kyrion-gateway` still requires the visible administrator step documented
in the handoff.

Start and restart buttons are intentionally not exposed yet. Lifecycle actions
must be Core-owned, restricted to a fixed allowlist and audited rather than
turning the Web application into a general process launcher.

## Operational lessons

- Core must bind to `0.0.0.0` for the Gateway and Voice Satellite. A Core
  process restarted with the default loopback bind caused a real Voice outage.
- A newly built JAR is not a deployed fix. The single-click correction did not
  become active until the old 22:01 process was replaced by the 22:14 build.
- Health checks must exercise the Pi-to-Core path, not only
  `127.0.0.1:8080` on Windows.
- A recoverable action-recognition or TTS failure must not terminate the entire
  Voice stream with HTTP 500. The observed dynamic-TTS failure remains a
  resilience follow-up even though the catalog-contract fix removed it from
  the normal light-command path.

## Next-session order

1. Physically press single twice with a two-second pause and verify one
   `bluetooth.power on=true` pair followed by one `on=false` pair.
2. Measure long-press latency from Zigbee event timestamp to Nanoleaf action
   completion; optimise only the measured slow segment.
3. Verify `Danke Velora` and `Vielen Dank Velora` physically close the session
   and rotate through approved responses.
4. Verify living-room Bluetooth brightness after dark.
5. Add a fixed/audio-safe Voice error response so unavailable dynamic TTS
   cannot convert a bounded failure into an HTTP 500 stream abort.
6. Package Core startup with the required LAN bind and add Pi-originated
   readiness to the service page before the demo is considered operationally
   stable.


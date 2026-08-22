# Device events and control closeout — 2026-08-23

## Outcome

This work session expanded the local-first owner slice in three areas: personal
data recovery, auditable retention, and physical device input. The resulting
implementation is useful, but the physical button-to-room path is not yet
closed as production-reliable. This checkpoint records both the delivered
behaviour and the rollout faults found during physical use.

## Personal data, retention and audit

- Personal backups can be encrypted with an owner passphrase, previewed before
  import and imported into another owner without exposing credentials.
- Import is owner-scoped, transactional and idempotent for retained source IDs.
- PostgreSQL backup and restore-verification scripts provide an operational
  recovery path separate from personal portable exports.
- Retention cleanup now supports preview, explicit confirmation and bounded
  owner-scoped deletion.
- Owner activity events are protected by HMAC integrity chains with a visible
  verification result.

## Physical devices added

The following devices were paired and registered through the Raspberry Pi
gateway and Zigbee2MQTT:

- Sonoff SNZB-03P motion sensor (`0xcc36bbfffe020c0d`);
- Sonoff SNZB-01P wireless switch (`0xf044d3fffef8debf`).

Core and Web contracts now distinguish device classes and typed state for
occupancy, battery, illumination, illuminance and button actions. Device
capabilities are derived from known models rather than from the accidental
presence of a momentary state field. Hue model `8720169364066` remains a light
even while a live value is temporarily unavailable.

## Wireless-switch bindings

The owner can configure `single`, `double` and `long` gestures from the device
overview. Each gesture can target either one power-capable device or every
power-capable device in a room and can toggle, turn on or turn off the target.
Bindings are persisted and validated in Core; the browser and gateway cannot
store arbitrary commands.

The gateway subscribes to bounded Zigbee2MQTT events and authenticates them to
Core. Core accepts the event quickly and executes the configured action through
the existing policy, capability, command and audit path.

Physical logs confirmed that all three gestures reach the gateway distinctly.
However, room execution was initially slow and sporadic because Core waited for
the whole action and the gateway subscribed to a Zigbee state confirmation only
after publishing the command. Core processing is now asynchronous and the
gateway subscribes before publishing. A longer repeated physical reliability
run is still required before this path is considered closed.

## Motion history

SNZB-03P occupancy changes are forwarded as authenticated gateway events and
persisted owner-scoped in Core. Repeated identical states are deduplicated. The
sensor card polls and displays the latest detected/clear transitions with
timestamps. The first persisted physical detection was recorded at
2026-08-22 21:53:40 CEST.

The first health implementation incorrectly issued every possible `/get`
property to every Zigbee device. This produced repeated Zigbee2MQTT converter
errors and duplicate sensor publications. Health collection is now
model-aware: Hue lights request only supported light state, while passive
Sonoff sensors and buttons rely on their published events.

## Unified device overview

- Device cards use category-specific visual accents for lights, sensors,
  switches and other devices.
- Empty state containers are no longer rendered.
- Sensors display motion history and switches display button bindings instead
  of light controls.
- All power-capable lights use the same card structure: detail control, live
  power, brightness and colour, quick power controls, management and room
  assignment.
- Gateway device state refreshes automatically every five seconds.
- Hue and Nanoleaf colours use provider-reported state. MELK-OA20 Bluetooth
  lights use the last successfully executed Kyrion command because the current
  protocol has no reliable colour readback.

The Bluetooth state implementation was initially tested locally but not copied
to the Pi. Physical commands therefore succeeded while the Web card continued
to show unknown values. The missing module was deployed and the latest
successful Core command history was used to restore the two known states:

- `Lampe Links`: on, brightness 100%, hue 313°, saturation 100%;
- `Lampe Rechts`: on, brightness 50%, hue 238°, saturation 100%.

The gateway heartbeat and Core database subsequently contained those values.
Future successful Bluetooth power, brightness and colour commands update the
gateway-owned state file.

## Operational status and verification

At closeout:

- Core health was `UP` on port 8080;
- Web served `/devices` on port 3000;
- `kyrion-gateway-agent.service` was active;
- the user-level `kyrion-voice-satellite.service` was active;
- Core: 111 tests passed;
- Web: lint, 28 tests and production build passed;
- Gateway agent: Ruff passed, 17 tests passed and 1 hardware-dependent test was
  skipped.

Core restarts temporarily interrupted the Voice Satellite during the session.
The satellite does not yet recover every active interaction cleanly after a
Core outage, so controlled Core rollout must restart or explicitly verify the
user-level satellite service until reconnect behaviour is hardened.

## Remaining acceptance work

1. Run at least twenty physical `single` room-toggle attempts and record event,
   command-start, device-confirmation and total latency.
2. Repeat for `double` and `long`, including rapid but valid successive input.
3. Verify multi-provider rooms and partial failure without delaying successful
   targets unnecessarily.
4. Verify SNZB-03P detected-to-clear timing and history after a Pi and Core
   restart.
5. Add a narrowly scoped, root-owned gateway deployment helper so routine
   updates do not depend on repeated interactive `sudo` commands.
6. Harden Voice Satellite reconnect behaviour across planned and unplanned Core
   restarts.

Do not treat green automated tests as physical acceptance for these items.
Close each only with observed hardware evidence.

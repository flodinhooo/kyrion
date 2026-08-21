# Bluetooth OA20 Light Integration — 2026-08-21

## Outcome

Kyrion now has a bounded, direct Bluetooth integration for the two locally
owned `MELK-OA20` colour lamps. Home Assistant is not in this command path.
The Web interface discovers an unapproved lamp, requires an explicit owner
name and Add action, and then controls it through Core's existing audited
asynchronous gateway-command flow.

The first lamp, `C7:7C:08:10:37:EA`, was added as `Lampe Rechts`. Physical Web
power control succeeded in both directions. Direct protocol validation also
confirmed red, green, blue, violet and cyan output. The second lamp,
`C7:7C:08:10:38:9B`, was found after an active Bluetooth scan and connection;
its final Web approval and physical control acceptance remain to be recorded.

## Architecture and implementation

- The unprivileged Raspberry Pi gateway agent lists only the explicitly
  supported Bluetooth model `MELK-OA20` and validates exact Bluetooth MAC
  addresses before invoking BlueZ tools.
- Core receives bounded Bluetooth candidates in the authenticated five-second
  heartbeat. Discovery does not create authority: the owner must explicitly
  name and add a candidate.
- Core persists the approved device with provider `bluetooth`, validates typed
  power, brightness and colour capabilities, enqueues commands, and records
  correlated outcomes through the same command-status boundary as Zigbee.
- The agent accepts only `bluetooth.power`, `bluetooth.brightness` and
  `bluetooth.color`; arbitrary Bluetooth or operating-system commands are not
  exposed.
- Web uses same-origin routes and provider-neutral device contracts. It never
  receives Bluetooth privileges or executes manufacturer protocol rules.

## Physically validated protocol

The lamp exposes service `FFF0`; command writes use characteristic `FFF3`.
Firmware readback returned `TQ31K0F10V106`. The following fixed nine-byte
messages were exercised on the physical lamp:

- power off: `7E 04 04 00 00 00 FF 00 EF`;
- power on: `7E 04 04 01 00 01 FF 00 EF`;
- select RGB mode: `7E 04 04 E0 01 01 FF 00 EF`;
- set RGB: `7E 07 05 03 RR GG BB 10 EF`;
- brightness: `7E 04 01 VV 01 FF FF 00 EF`, where `VV` maps 0–100 percent to
  0–255.

Power and colour are physically accepted. Brightness must be repeated in a
dark room before its visual behaviour is considered accepted.

## State-reporting boundary

The OA20 protocol did not provide a reliable readable current colour,
brightness or power state. The gateway therefore persists the last command
that Kyrion successfully wrote and includes that state in subsequent
heartbeats. Web refreshes after command completion and labels the provider as
`Bluetooth · kyrion-node` instead of incorrectly falling through to Nanoleaf.

This is truthful command-state reporting, not independent device telemetry.
Changes made through another application or a physical power interruption may
leave Kyrion's displayed state stale. A later protocol investigation may add
verified readback, but the UI must not claim live device state until that is
proven.

## Verification

- Gateway agent: Ruff passed; 15 tests passed and one Linux-only test was
  skipped on Windows.
- Web: 22 tests passed; ESLint and the Next.js production build passed.
- Core and Web power commands physically switched `Lampe Rechts` off and on.
- Direct Bluetooth tests physically produced the expected RGB colours.
- The state-persistence update was copied to `/tmp/bluetooth.py` on
  `kyrion-node`. Final activation requires the owner to run
  `sudo sh /tmp/activate-gateway-agent-update.sh`; post-activation UI state
  verification was not completed before this closeout.

## Next session

1. Activate the prepared gateway update and set a distinct colour through Web;
   verify the card reports the stored colour after the next heartbeat.
2. Add and name `C7:7C:08:10:38:9B`, then verify power and colour independently
   so the two lamps cannot be confused.
3. Repeat brightness tests after dark and document the useful lower bound.
4. Add an owner-triggered, time-bounded Bluetooth search action so a new lamp
   can be found without SSH or a manual `bluetoothctl` session.
5. Test disconnect/reconnect, gateway restart and lamp power-cycle behaviour;
   keep the persisted-state limitation visible.

Do not commit local gateway credentials, Bluetooth pairing material or private
device configuration.

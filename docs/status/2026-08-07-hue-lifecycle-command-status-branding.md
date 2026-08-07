# Hue Lifecycle, Command Status and Branding Session — 2026-08-07

## Outcome

Kyrion's local-device slice is now substantially closer to a flow that can be
given to another household without manual database or Raspberry Pi work. Two
Philips Hue colour lamps are owner-approved, named, visible on `/home`, assigned
to the persisted `Gang` room and controllable through the outbound-only gateway
boundary. Adding a supported Hue automatically configures its device-local
power-on behaviour to recover the last colour and brightness after a cold power
cycle, without requiring Core or the PC to be online.

The device UI separates the editable owner name from immutable hardware
identity, displays live Hue and Nanoleaf power, brightness and colour state, and
uses a red Off / green On convention. Nanoleaf state refreshes automatically;
gateway command polling is independent from health collection and runs every
250 ms.

The first asynchronous Zigbee command-status slice is implemented. Hue commands
return a command identifier immediately, and Web polls an owner-scoped Core
status endpoint to display pending, succeeded or failed state. Owner-confirmed
removal publishes a bounded Zigbee2MQTT remove request through the Pi agent and
deletes the persistent Core record only after gateway success. Physical removal
was intentionally not performed because it would destroy a working pairing.

Kyrion's approved SVG identity is integrated. The sidebar uses the full Kyrion
lockup without duplicate text or tagline, the login surface uses the standalone
K-Core mark, and both switch between approved light and dark variants according
to the active theme. The official transparent favicon replaces the legacy
Vercel favicon and temporary generated icon. `branding/brand-guide.md` is the
source of truth; Web serves runtime copies from `apps/web/public/branding`.

## Accepted devices and persistence

- `Philips Hue Gang`, IEEE `0x001788010feda8ac`, room `Gang`.
- `Phillips Hue EIngang`, IEEE `0x001788010fdcc07d`, room `Gang`.
- PostgreSQL verification confirmed both stable Core UUIDs, editable names,
  IEEE endpoint identities and persisted room relationships.
- Both lamps use `hue_power_on_behavior=recover`. This setting lives on the lamp
  and does not depend on the PC, Web, Core or Pi remaining online afterwards.
- Rename and room changes persist through Core and survive browser, Core and
  gateway restarts.

## Implemented flows

### Discovery and Home

- `/devices/add` presents supported Zigbee and local-network paths.
- Discovery is explicit; heartbeat visibility alone creates no approved device.
- A Zigbee candidate requires an owner-entered name and explicit Add action.
- Core creates or reconciles the database record and `/home` displays it.
- Home shows the owner name separately from hardware identity and current state.

### State and command latency

- Pi heartbeat reports Hue power, percentage brightness, hue, saturation and
  colour temperature every five seconds.
- Nanoleaf state refreshes automatically every ten seconds for a bounded maximum
  of 20 connections.
- Gateway health remains at five seconds while commands are checked every
  250 ms, removing the former approximately five-second control delay.

### Asynchronous commands and removal

- `POST /v1/device-commands/async` validates one owner-scoped Zigbee target,
  enqueues a typed command and returns `202` with its command ID.
- `GET /v1/device-commands/{id}` exposes only the owner's pending, running,
  succeeded or failed state and bounded error code.
- Quick controls and the Hue dialog show accessible live command state.
- Removing a Hue requires confirmation. Core resolves its gateway, the agent
  publishes only `zigbee2mqtt/bridge/request/device/remove`, and Core deletes
  the connection after confirmed execution. It can then be paired and added
  again through the normal discovery flow.
- Existing AI and room-level aggregate commands retain their synchronous result
  contract for now; the UI slice did not silently change AI execution semantics.

## Branding and browser identity

- Sidebar: `branding/logo/kyrion-light.svg` and `kyrion-dark.svg`.
- Login/compact mark: `branding/logo/k-light.svg` and `k-dark.svg`.
- Browser: transparent `branding/favicon/favicon.svg`.
- Titles are route-specific, such as `Zuhause · Kyrion`, instead of repeating
  `Kyrion — Local Intelligence` in every tab.
- `BrandAsset` is the reusable theme-aware Web component.
- The old `favicon.ico`, temporary `icon.svg`, CSS-drawn K, duplicate Kyrion text
  and sidebar tagline are no longer used.

## Voice Satellite preparation

A read-only audio inventory on `kyrion-node` found:

- no ALSA capture device;
- no USB microphone, speaker, ReSpeaker or other USB audio device;
- only the two Raspberry Pi HDMI playback outputs;
- no installed Voice Satellite or Wyoming service.

A placeholder daemon without capture hardware would provide no useful slice.
After microphone and speaker connection, record stable USB identity, verify ALSA
capture/playback, run acoustic tests, then introduce the smallest authenticated
satellite-to-Core contract. Voice remains independent from Zigbee and has no
direct device-control authority.

## Running topology at handoff

```text
Browser -> Web production build :3000 -> same-origin API
  -> Kyrion Core :8080 -> PostgreSQL
  -> persisted owner-scoped gateway queue
  -> kyrion-gateway-agent on kyrion-node
       command polling: 250 ms; heartbeat: 5 s
  -> loopback Mosquitto -> Zigbee2MQTT -> Sonoff coordinator -> two Hue lamps

Kyrion AI :8000 -> local Ollama / gemma3:4b
```

The Pi agent is active with `--interval 5 --command-interval 0.25` and contains
the new bounded `zigbee.remove` handler. Core and AI health endpoints were
healthy; rebuilt branding assets returned HTTP 200 as `image/svg+xml`.

## Verification

- Core Gradle tests passed and the Spring Boot JAR built.
- Web: 15 tests, ESLint and Next.js production build passed.
- Gateway: Ruff passed; 5 tests passed and 1 Linux-only test was skipped on
  Windows as designed.
- Removal coverage verifies the exact bridge topic and bounded IEEE payload.
- `git diff --check` passed.
- Both Hue room assignments were checked directly in PostgreSQL.
- The deployed Pi agent is active with fast polling and the removal handler.

## Security boundaries retained

- Core owns identity, owner scope, validation, persistence, policy and audit.
- Web receives no MQTT, radio or gateway credentials.
- The outbound-only Pi agent supports a fixed typed command set, not a shell.
- MQTT remains loopback-only and removal requires explicit UI confirmation.
- Command-status lookup is owner-scoped.
- No secrets or private keys are documented.

## Known limitations

1. Removal has automated boundary coverage but was not physically executed on a
   working Hue lamp in this session.
2. Async status needs cross-owner, timeout, malformed-payload, adapter-failure,
   retry and idempotency tests before wider scaling.
3. An unapproved candidate has no dedicated Reject action yet.
4. Zigbee still reuses `integration_connection`; introduce a provider-neutral
   device schema before exposing a plugin contract.
5. Heartbeat stale/offline and restart/recovery behaviour needs focused tests.
6. Backup restore, Pi reboot, network-loss, rollback and clean-room onboarding
   remain unproven.
7. USB voice hardware and the ZBT-2 Thread/Matter adapter are not accepted yet.
8. Browsers may cache the old favicon until refreshed.

## Exact next-session order

1. Read this handoff, `docs/status/README.md` and `docs/status/TODO.md`; preserve
   unrelated uncommitted user changes.
2. Verify Core, Web, AI, PostgreSQL and Pi services. Confirm both Hues remain in
   `Gang`, retain recover behaviour and respond from `/home`.
3. With the owner's chosen lamp, manually exercise remove and re-pair: database
   deletion, Zigbee departure, candidate rediscovery, explicit name/Add and room
   assignment.
4. Add async ownership, timeout, failure, retry and idempotency tests and decide
   how completed async commands update observations.
5. Add candidate Reject UX and define whether Reject only hides a candidate or
   also requests network removal.
6. Once USB audio is connected, perform Voice Satellite hardware acceptance.

Read-only Pi checks:

```bash
systemctl status kyrion-gateway-agent zigbee2mqtt mosquitto --no-pager
journalctl -u kyrion-gateway-agent -u zigbee2mqtt -u mosquitto -n 100 --no-pager
arecord -l
aplay -l
lsusb
```

Never paste `/etc/kyrion-gateway/agent.json`, Zigbee network configuration,
credentials or private SSH keys into chat, issues or documentation.

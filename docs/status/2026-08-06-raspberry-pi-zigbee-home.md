# Raspberry Pi, Zigbee and Home Integration Session — 2026-08-06

## Outcome

The first physical Zigbee slice works end to end. An authenticated owner can
open a bounded pairing window in gateway settings, pair a Philips Hue lamp via
the Sonoff coordinator on `kyrion-node`, see it automatically in the shared
Home catalog, assign it to a room, and control power, brightness and colour
from `/home`. The owner physically verified lamp control. Gateway settings are
an onboarding and diagnostics surface; daily controls belong to Home.

## Running topology

```text
Browser /home or /settings/gateways
  -> Next.js same-origin API
  -> Kyrion Core at 192.168.1.107:8080
  -> persisted typed command queue (Flyway V12)
  -> authenticated outbound-only gateway agent (5-second polling)
  -> loopback MQTT -> Zigbee2MQTT -> Sonoff ZBDongle-E -> Hue lamp
```

Core owns owner scope, validation, persistence and audit. The browser has no
MQTT or gateway credentials. The Pi exposes no inbound Kyrion command, shell or
MQTT endpoint; the agent retrieves bounded commands and reports their result.

## Accepted hardware and runtime

- Raspberry Pi 5, 8 GB, Debian 13 ARM64, approximately 64 GB microSD.
- `kyrion-node.local`, SSH user `flodinho`, dedicated Ed25519 key.
- Reserved Ethernet `192.168.1.116`; reserved Wi-Fi `192.168.1.115`. Ethernet
  is active.
- Gateway agent `0.1.0` as hardened `kyrion-gateway-agent.service`, installed
  at `/opt/kyrion-gateway`; protected config at
  `/etc/kyrion-gateway/agent.json`.
- Sonoff ZBDongle-E stable identity:
  `/dev/serial/by-id/usb-Itead_Sonoff_Zigbee_3.0_USB_Dongle_Plus_V2_3a2eabb8d8ffef11ba3e91256d9880ab-if00-port0`.
- Zigbee2MQTT 2.10.1, Ember firmware 7.4.4, Zigbee channel 15. Installed under
  `/opt/zigbee2mqtt`, data under `/var/lib/zigbee2mqtt`, managed by
  `zigbee2mqtt.service`.
- `mosquitto.service` binds only to `127.0.0.1:1883`; the Zigbee2MQTT frontend
  is disabled.
- Paired Philips Hue White and Color Ambiance A60 E27 1100, model
  `8720169364066`, IEEE `0x001788010feda8ac`.
- Root-only snapshots:
  `/var/backups/kyrion/zigbee/initial-network` and
  `/var/backups/kyrion/zigbee/first-hue-paired`.

Never document passwords, node credentials, radio keys, MQTT secrets or
private SSH keys.

## Implemented user flows

Pairing starts from Plugins -> Zigbee -> gateway settings. It opens a visible
180-second window with a countdown and displays coordinator, service and paired
device diagnostics. The page intentionally has no normal lamp controls.

On `/home`, supported paired Zigbee devices are synchronised into the
owner-scoped Core catalog and initially appear under Unassigned. The existing
room-assignment flow works. Quick power and the device dialog route power,
brightness and colour through Core and the gateway queue. Heartbeats update
availability and state approximately every five seconds.

## Implementation landmarks

- `services/gateway-agent`: health collection, authenticated Core client,
  command polling and local Zigbee MQTT adapter.
- `services/core`: gateway identity/heartbeat, Zigbee catalog sync, command
  validation, persisted queue and completion audit. Flyway V11 owns gateway
  identity/health; V12 owns gateway commands.
- `apps/web`: gateway pairing/diagnostics plus Home Zigbee cards, room
  assignment, quick power and detailed controls.
- `infrastructure/nodes/kyrion-node`: repeatable development provisioning and
  deployment scripts.

The Zigbee catalog entry currently reuses `integration_connection` with
provider `zigbee`, a stable Core UUID and the IEEE address as provider endpoint.
Web receives only bounded catalog identity and capabilities.

## Security decisions

- Core port 8080 is allowed only from Pi addresses `192.168.1.115` and
  `192.168.1.116`, not the general LAN or internet.
- The agent is unprivileged, with no unrestricted sudo, Docker socket or
  general remote-command facility.
- MQTT is loopback-only; the Zigbee2MQTT frontend is off.
- Pairing is closed by default and opens only through an explicit timed action.
- Commands are typed, owner/node scoped, persisted and correlated before local
  execution. Raw MQTT topics and secrets never reach Web.

## Verification completed

- Core tests and boot JAR build passed.
- Web tests (15), lint and production build passed after moving controls Home.
- Gateway-agent Ruff checks and tests passed; Linux-only collector tests were
  skipped on Windows as designed.
- Core restarted healthy with the current JAR.
- The real heartbeat reported the coordinator, Hue and live state.
- The owner physically confirmed Web control of the lamp.

## Known limitations and technical debt

1. Supported paired devices are auto-imported after explicit pairing. Add a
   discovery inbox with candidate, approve, name, reject, remove and re-pair.
2. Zigbee reuses `integration_connection` and stores empty credential byte
   arrays. Replace this internal shortcut with a stable provider-neutral device
   schema before making it a plugin contract.
3. Home lacks Zigbee colour temperature, scenes, rename, remove and
   leave-network handling.
4. Zigbee observations are heartbeat-driven. Home's explicit refresh currently
   refreshes Nanoleaf only; stale/offline reconciliation needs focused tests.
5. Core currently waits up to roughly 12 seconds for command completion by
   polling in the request thread. Replace this with an asynchronous status API
   and visible pending/result UI before scaling.
6. Add command tests for cross-owner access, timeout, adapter failure, malformed
   payload, retries and idempotency. Manual colour testing left superseded
   commands as audited `failed/SUPERSEDED`; retention policy is undefined.
7. Velora's proven path remains Nanoleaf-focused. Deliberately extend and test
   provider-neutral AI control before claiming Zigbee voice control.
8. Backups exist but restore is unproven. Pi reboot, network-loss, update and
   rollback acceptance remain open.
9. Wi-Fi is disconnected and reports `no-secrets` during wait-online; Ethernet
   is stable. Preserve the profile until an explicit fallback test.
10. Use a USB extension at final placement. ZBT-2 Thread/Matter and USB voice
    hardware are not attached or accepted.
11. SSH/sudo provisioning is a development path. Later build guided bilingual
    onboarding and reset this Pi for a clean-room non-technical owner test.

## Exact next-session order

1. Re-read this handoff. Verify Core and `kyrion-gateway-agent`, Mosquitto and
   Zigbee2MQTT. Confirm Hue remains controllable on `/home` after refresh.
2. Build the Core-owned Zigbee discovery inbox and explicit
   approve/name/reject/remove lifecycle while preserving the paired device.
3. Replace blocking command completion with typed asynchronous status and Web
   pending/failure states; add ownership, timeout, failure and retry tests.
4. Stabilise provider-neutral persistence/capabilities; add rename and
   offline/stale reconciliation.
5. Prove backup restoration and Pi reboot/network-loss recovery.
6. Then start the independent ZBT-2 Thread/Matter slice, followed by USB voice.
   Radio discovery alone is not integration success.

Read-only node checks:

```bash
systemctl status kyrion-gateway-agent zigbee2mqtt mosquitto --no-pager
journalctl -u kyrion-gateway-agent -u zigbee2mqtt -u mosquitto -n 100 --no-pager
```

Never paste credentials from `/etc/kyrion-gateway/agent.json` or Zigbee network
configuration into a chat or issue.

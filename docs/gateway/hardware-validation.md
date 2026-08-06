# Gateway Hardware Validation

Last updated: 2026-08-06

## Known from purchase information

- Raspberry Pi 5 starter kit
- 8 GB RAM
- 64 GB microSD card
- Raspberry Pi OS preinstalled
- Ethernet currently connected
- integrated Wi-Fi and Bluetooth
- Creative Pebble V3 USB speakers
- Delock USB omnidirectional condenser microphone
- Sonoff ZBDongle-E planned as the dedicated Zigbee coordinator
- Home Assistant Connect ZBT-2 planned as the dedicated Thread radio

## Verified inventory

The read-only SSH inventory on 2026-08-06 confirmed:

- Debian 13.6 ARM64 with Raspberry Pi kernel `6.18.39+rpt-rpi-2712`;
- four Cortex-A76 CPU cores and 7.9 GiB usable memory;
- 58.6 GiB microSD capacity with approximately 48 GiB free;
- Ethernet at the reserved `192.168.1.116` address plus global and link-local
  IPv6 connectivity;
- synchronised time in `Europe/Zurich`;
- integrated Bluetooth powered and available;
- 42.2 degrees Celsius, with no recorded throttling;
- membership of `dialout`, `audio`, `video`, `plugdev`, `netdev`, GPIO, I2C,
  and SPI groups for the interactive owner account;
- no Docker, Podman, Home Assistant, USB serial radio, USB microphone, or USB
  speaker detected yet.

The host reports a degraded system state only because
`NetworkManager-wait-online.service` failed. Ethernet and SSH remained
operational. The service reached its 60-second timeout during boot. The active
Ethernet profile and an enabled but currently disconnected Wi-Fi autoconnect
profile are the relevant observed inputs. The Wi-Fi profile is a probable cause,
but this has not been proven and is intentionally unchanged because it may
later provide network fallback.

The later NetworkManager journal confirmed the cause: Ethernet obtained its
reserved lease and reached the activated state within about four seconds, while
the Wi-Fi profile repeatedly failed association and eventually reported
`no-secrets`. NetworkManager did not mark startup complete before that attempt
ended. The agent reports the current Wi-Fi interface as disconnected and does
not treat this historical wait-online failure alone as a live node degradation;
the profile remains intact for a later explicit fallback test.

## Validation checklist

- [x] Confirm exact operating-system release, kernel, and architecture.
- [x] Confirm 8 GB memory and Cortex-A76 CPU topology.
- [x] Confirm microSD capacity, filesystem, and free space. Media health and
  recovery remain unverified.
- [x] Confirm stable Ethernet address and reserved IPv4 lease.
- [ ] Confirm multicast DNS and temporary
  network-loss recovery.
- [x] Confirm global IPv6 connectivity and time synchronisation.
- [x] Confirm current throttling state and temperature. Load and restart tests
  remain pending.
- [x] Confirm Bluetooth controller. Bounded discovery remains pending.
- [ ] Detect microphone and speakers and record stable ALSA/PipeWire identities.
- [ ] Test capture and playback without retaining unnecessary voice recordings.
- [ ] Attach the ZBDongle-E through a USB extension and record its stable USB
  identity before configuring Zigbee.
- [ ] Attach the ZBT-2 through a separate USB extension and record its stable
  USB identity before configuring Thread/OTBR.
- [ ] Validate Zigbee pairing, state, commands, events, coordinator backup, and
  restore.
- [ ] Validate Thread formation, OTBR health, Matter commissioning, events,
  backup coverage, and recovery.
- [ ] Validate authenticated gateway heartbeat, restart, update, rollback, and
  temporary-network-loss behaviour.
- [ ] Expose only sanitised structured health and diagnostics through Core to
  the Web application.

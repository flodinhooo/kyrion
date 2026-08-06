# Development Hardware Roadmap

This document records the hardware ordered and delivered in August 2026 for
Kyrion's next local integration and infrastructure slices. The Raspberry Pi is
now inventoried and registered; radio, protocol-test and USB voice hardware
remain planned until explicitly validated below.

The equipment is for Kyrion development and validation only. Its purpose is to
prove provider-neutral device, event, automation and voice contracts against
real hardware before a broader plugin ecosystem is considered.

## Gateway node

The ordered Raspberry Pi 5 starter kit (8 GB) is intended to become a permanent
local gateway node. It will communicate with Kyrion Core over the local network
and is expected to host the following edge-facing responsibilities:

- the first Velora voice satellite;
- a Zigbee coordinator and bridge;
- an OpenThread Border Router (OTBR);
- a Bluetooth gateway;
- local integration processes that require direct access to radio hardware.

The Raspberry Pi is an integration host, not an alternative authority. Kyrion
Core continues to own authentication, authorisation, command validation,
confirmation policy, persistence and audit logging. Edge processes must expose
bounded, typed operations and must not provide unrestricted remote shell access
to Core, the AI service or the browser.

The first deployment keeps Kyrion Core on the development PC or a later server.
Larger local AI models are not assumed to run on the gateway. The Pi may buffer
bounded state and events during temporary Core or network unavailability. A
future ability to continue a small set of local rules requires separately
versioned policies, expiry, conflict handling and delayed audit delivery and is
therefore not part of the initial gateway slice.

## Radio adapters

### Zigbee

- **Adapter:** Sonoff ZBDongle-E
- **Role:** dedicated Zigbee coordinator
- **Constraint:** reserved exclusively for Zigbee

### Thread

- **Adapter:** Home Assistant Connect ZBT-2
- **Role:** dedicated Thread radio for OTBR on the Raspberry Pi
- **Constraint:** reserved exclusively for Thread and Matter over Thread

### Bluetooth

Bluetooth experiments will use the Raspberry Pi's integrated Bluetooth radio.
No separate Bluetooth adapter is currently planned.

Keeping Zigbee and Thread on dedicated adapters reduces operational ambiguity
and lets each radio stack be upgraded, diagnosed and recovered independently.
Final firmware, USB device mapping and radio-stack choices will be recorded
after the hardware has arrived and has been validated.

## Voice hardware

The Raspberry Pi will use:

- a USB conference microphone;
- a USB speaker.

Together these will form the first Velora voice satellite. The satellite should
capture and play audio locally and communicate with a Core-controlled voice
pipeline through an authenticated, explicit protocol. It must not execute
device actions directly. Recognised intent or AI-proposed actions must pass
through the same Core validation, permission and audit path as web requests.

## Initial test devices

### Zigbee

- 2 x Philips Hue White & Color Ambiance E27 lamps;
- Sonoff SNZB-01P wireless switch;
- Sonoff SNZB-03P motion sensor.

### Wi-Fi

- Shelly H&T Gen3 temperature and humidity sensor;
- myStrom WiFi Switch 2 with energy monitoring.

### Matter over Thread

- Aqara Door and Window Sensor P2.

These named products are test fixtures, not domain concepts. Device-facing
features in Web, automations and AI tools must depend on stable Kyrion device,
capability and event contracts rather than Zigbee clusters, Matter details or
manufacturer APIs.

## Target topology

```text
Kyrion Web / Velora
          |
          | typed HTTP/JSON contracts
          v
      Kyrion Core
          |
          | validated commands, state and events
          v
Raspberry Pi gateway node
  |-- Zigbee adapter (Sonoff ZBDongle-E)
  |-- Thread adapter and OTBR (Home Assistant Connect ZBT-2)
  |-- Bluetooth adapter (integrated Raspberry Pi radio)
  |-- Wi-Fi integration adapters
  `-- Velora voice satellite
```

The first deployment boundary is now proven with Core on the development PC and
an unprivileged native Python gateway agent on Debian 13 ARM64. The agent sends
authenticated typed health heartbeats and has no sudo, Docker socket or general
command surface. Core may eventually run on the Pi, but integrations must still obey
the same logical trust boundary and must not bypass Core merely because
processes share a host.

## Protocol-neutral model

Automations and user interfaces must address capabilities and events, never a
transport protocol directly. Representative concepts include:

```text
Capabilities                       Events
--------------------------------   --------------------------------
power.set                          button.pressed
light.setBrightness                motion.detected
light.setColour                    contact.opened
climate.readTemperature            contact.closed
climate.readHumidity               climate.temperatureChanged
energy.readPower                   device.availabilityChanged
```

Names and payloads above are illustrative, not stable contracts. The first
implementation slice must define typed identifiers, value constraints, units,
timestamps, source identity, quality/availability state and versioning before
these contracts are treated as public or plugin-facing.

## Velora device control

Velora should become a conversational control surface for every device and
capability that Kyrion makes available to the authenticated owner. A request
such as "turn on the Nanoleafs in the living room" should eventually use the
same trusted command path whether it originates in text chat or at a voice
satellite:

```text
Owner request in text or voice
          |
          v
Velora proposes a typed capability command and target selector
          |
          v
Kyrion Core resolves owner-visible rooms and devices
          |
          v
Core validates capability, arguments, permissions and confirmation policy
          |
          v
Integration adapter executes the command
          |
          v
Core records the correlated result and Velora reports it to the owner
```

Velora must not receive direct Nanoleaf, Zigbee, Thread, Bluetooth or Wi-Fi
control. Core supplies only an owner-authorised tool and capability catalogue,
rejects invented or unavailable targets, and asks for clarification rather
than guessing when a room or device selector is ambiguous. Destructive,
costly, privacy-sensitive or safety-relevant actions require the applicable
confirmation policy. Routine actions such as switching an already authorised
light may be eligible for immediate execution under an explicit owner policy.

## Software preparation

Preparation can begin before the hardware arrives, but should proceed as small
vertical slices rather than speculative infrastructure.

1. **Device and capability foundation**
   - define provider-neutral device identity, state and capability contracts;
   - model online, offline, degraded and unknown states explicitly;
   - adapt the existing Nanoleaf integration to prove the abstraction.
   - expose one Core-owned command path shared by Web, automations and Velora.
2. **Integration management**
   - list configured and discoverable integrations separately;
   - expose connection health and setup requirements without leaking secrets;
   - keep credentials and privileged configuration in Core.
   - offer Observe, Control and Manage access profiles backed by granular Core
     permissions;
   - introduce an optional Home Assistant adapter for breadth while keeping
     native Nanoleaf as the reference integration.
3. **Discovery and gateway registration**
   - define an authenticated gateway identity and heartbeat;
   - separate discovered candidates from approved, paired devices;
   - require user confirmation for pairing, removal and credential changes.
   - create a pre-change restore point before pairing, migration, removal or
     material adapter configuration.
4. **Events and automations**
   - define typed, replay-safe device events and correlation identifiers;
   - route automation commands back through Core policy and audit logging;
   - begin with one real trigger-to-action slice after hardware validation.
5. **Voice pipeline**
   - replace the current browser-dependent prototype incrementally;
   - define satellite registration, health, audio-session and interruption
     contracts;
   - preserve an explicit boundary between speech/intent processing and action
     execution.
   - return Core-confirmed action results to the satellite for spoken feedback.
6. **Adapter and plugin evolution**
   - implement first-party adapters behind internal versioned contracts;
   - prove permissions, lifecycle, isolation, updates and rollback before any
     third-party or marketplace runtime is introduced.

## Web application preparation

The Web application can be extended without encoding assumptions about the
ordered products. Useful provider-neutral surfaces are:

- a device manager for identity, room assignment, state and capabilities;
- an integration manager for setup, health and removal;
- a discovery inbox for unapproved devices and gateways;
- gateway and voice-satellite health views;
- automation building blocks based on capability commands and typed events;
- clear confirmation and activity views for sensitive actions.

All user-facing additions require German and English locale entries. The
browser must communicate through same-origin routes and must never receive
radio credentials, integration secrets or unrestricted gateway access.

## Validation after delivery

Hardware arrival does not by itself complete this roadmap. Each integration
should be accepted through a narrow end-to-end test with recorded results:

- [x] the Raspberry Pi can register securely and report health to Core;
- [x] the agent service restarts and resumes authenticated heartbeats;
- [ ] a full Pi reboot and temporary network loss are visible and recover;
- Zigbee devices can be discovered, explicitly paired, read and controlled;
- the Thread network and OTBR can be commissioned and recovered safely;
- the Matter sensor produces provider-neutral contact events;
- Wi-Fi devices expose state and commands through integration adapters;
- Bluetooth discovery is bounded and does not automatically trust devices;
- the voice satellite supports capture, playback and a Core-validated action;
- restart, temporary network loss and unavailable-device behaviour are visible;
- a restore-point manifest records applicable Core, gateway, Zigbee, Thread and
  provider backup coverage before protected changes;
- created backups and successfully restore-verified backups remain visibly
  distinct;
- important setup and command activity carries actor and correlation data;
- no secret is exposed to the browser, logs or AI service.

Implementation details and completed validation results should be added to the
status documentation once the hardware is available.

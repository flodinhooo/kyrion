# Gateway Architecture

## Status

This document records the initial boundary for the planned authenticated
Raspberry Pi gateway. The gateway software and protocol adapters are not yet
implemented.

## Boundary

```text
Kyrion Web
    |
    v
Kyrion Core
    |
    v
Authenticated gateway agent
    |-- Home Assistant adapter
    |-- Zigbee service and dedicated coordinator
    |-- OpenThread Border Router and dedicated Thread radio
    |-- Matter service
    |-- Bluetooth adapter
    `-- Voice satellite capture and playback
```

Core remains authoritative for identity, permissions, policy, confirmation,
persistence, command validation, and correlated audit. Web presents state and
collects intent. The AI service may propose typed capabilities but never
receives provider credentials, radio credentials, or arbitrary gateway access.

The gateway agent reports bounded health and capabilities and executes only
typed, Core-authorised operations. Protocol-specific identifiers and commands
remain behind adapters.

## Radio allocation

The intended first allocation is one dedicated radio per protocol:

- Sonoff ZBDongle-E for Zigbee;
- Home Assistant Connect ZBT-2 for Thread/OpenThread Border Router.

Zigbee and Thread/Matter are validated as independent vertical slices. Kyrion
uses mature protocol implementations and does not implement its own Zigbee,
Thread, or Matter stack.

## Observability

The user interface will consume safe, structured health information from Core.
Raw service logs remain an Expert-mode diagnostic source and must be filtered
for credentials, personal data, and voice content before presentation.

The first gateway vertical slice precedes radio onboarding and exposes:

- stable Core-owned node identity and display name;
- authenticated connection state and last heartbeat;
- operating-system and gateway-agent versions;
- temperature and throttling state;
- memory and persistent-storage capacity;
- bounded Ethernet, Wi-Fi, IPv6, and Bluetooth health;
- typed health entries for installed protocol and voice services.

Core persists the latest bounded observation and applies an explicit staleness
policy. Web reads Core state and never polls the node, Home Assistant, or a
protocol container directly. Developer logs remain separate from owner-visible
activity events and sanitised diagnostic summaries.

# Kyrion

> A local-first platform for connecting devices, services, media and artificial intelligence.

Kyrion is a modular personal infrastructure platform designed to unify otherwise
isolated parts of a user's digital environment.

It provides one coherent interface for devices, services, media systems,
automations and AI-assisted workflows while keeping users in control of their
infrastructure and data.

Kyrion begins as a personal project built around real use cases. It is intended
to grow incrementally without introducing unnecessary complexity before it is
needed.

## Vision

Modern digital environments are fragmented across many applications,
manufacturers, cloud services and proprietary ecosystems.

Kyrion aims to provide a consistent layer above these systems.

The platform should:

- run primarily on hardware controlled by the user;
- connect devices and services through modular integrations;
- remain usable without artificial intelligence;
- offer AI as an optional and controlled interaction layer;
- work locally whenever practical;
- remain understandable, secure and auditable;
- provide a modern and intuitive user experience.

Read the full [project vision](docs/vision.md).
The market-informed product focus and build-versus-integrate boundary are
defined in [Product Strategy](docs/product-strategy.md).

## Core principles

Kyrion is guided by the following principles:

- Local first
- Privacy by default
- AI is optional
- Controlled and auditable actions
- Modular integrations
- Useful before impressive
- Progressive complexity
- Offline-friendly operation
- Secure defaults
- Beautiful software
- Internationalisation from the beginning

Read all [project principles](docs/principles.md).

## Implemented first use case

Kyrion controls existing Nanoleaf installations through the official local
OpenAPI. The current development installation runs this slice end to end.

Implemented behaviour includes:

- automatic controller discovery through mDNS/Bonjour;
- owner-specific physical API authorisation;
- reading the current device state;
- switching the panels on and off;
- changing brightness;
- setting colour and colour temperature;
- listing and activating controller-stored scenes with palette previews;
- encrypted persistence of per-owner controller credentials;
- persistent rooms and device-to-room assignments;
- a room dashboard with live status, quick actions and device dialogs;
- displaying connection and API errors;
- supporting German and English user interfaces.

The current slice deliberately does not provide:

- a dedicated mobile application;
- Nanoleaf cloud-account or undocumented cloud API access;
- public registration or public internet exposure;
- a general third-party plugin runtime or public marketplace;
- remote access.

These components will only be introduced when a real use case requires them.

## Current architecture

```text
┌─────────────────────┐
│   Web Application   │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│     Kyrion Core     │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
┌────▼────┐ ┌────▼─────────┐
│ Devices │ │ Optional AI  │
└─────────┘ └──────────────┘
```

The browser communicates only with same-origin Next.js routes. Kyrion Core owns
users, sessions, rooms, integration connections, encrypted credentials,
command validation and activity logging. Only Core communicates with the
Nanoleaf local API. PostgreSQL persists owner-scoped state, while the optional
AI service and Ollama remain outside the device-execution boundary.

Read the full [architecture documentation](docs/architecture.md).
For the implemented device slice, see the
[Nanoleaf integration documentation](docs/nanoleaf-integration.md).

## Repository structure

Kyrion is maintained as a monorepo.

```text
kyrion/
├── apps/
│   ├── web/
│   └── mobile/
├── services/
│   ├── core/
│   └── ai/
├── packages/
│   └── api-contracts/
├── infrastructure/
├── docs/
├── .editorconfig
├── .gitignore
└── README.md
```

### Applications

`apps/web`

The main browser-based interface for configuration, dashboards, device control
and assistant interactions.

`apps/mobile`

The planned mobile application for quick actions, notifications and assistant
access.

### Services

`services/core`

The Kotlin and Spring Boot authoritative backend. It owns local authentication,
sessions, conversations, personal memory, rooms, integration connections,
encrypted credentials, validated Nanoleaf commands and the PostgreSQL-backed
activity log.

`services/ai`

The implemented optional AI service responsible for local chat streaming and
model-provider abstraction. It does not execute device commands directly.

### Shared packages

`packages/api-contracts`

Shared API definitions and generated client contracts.

### Infrastructure

`infrastructure`

Local PostgreSQL container configuration is implemented. Further deployment,
monitoring and backup configuration remains planned.

### Documentation

`docs`

Product vision, principles, architecture, roadmap and technical decisions.

## Languages and internationalisation

Kyrion will support German and English from the beginning.

English is used as the primary technical language for:

- source code;
- variable and function names;
- API contracts;
- commit messages;
- documentation;
- logs intended for developers.

The user interface supports:

- German: `de`
- English: `en`

User-facing text must not be hardcoded directly into interface components.
Translations should be managed through dedicated locale files.

English acts as the fallback language when a translation is unavailable.

The language preference should later be stored per user or installation.

## Assistant identity

Kyrion is the name of the platform.

Velora is the current working name for the optional assistant personality.

Assistant identity, voice and personality may later be configurable. Possible
options could include:

- Velora
- Kyrion
- custom assistant names
- different voices and personalities

The platform itself must not depend on one particular assistant identity.

## Development approach

Kyrion follows a vertical-slice development approach.

Each milestone should deliver one complete and usable capability across the
required layers instead of creating many disconnected technical components.

The first vertical slice is:

```text
Kyrion Web
    ↓
Nanoleaf server-side client
    ↓
Nanoleaf local API
    ↓
Physical light panels
```

The first success criterion is simple:

> A user can open Kyrion Web and reliably control the existing Nanoleaf panels
> without using the official Nanoleaf application.

## Project status

Kyrion is currently a working local-first prototype. Local text chat,
browser-backed voice, authentication, conversation persistence, explicit
personal memory, the activity log, Nanoleaf control and the room dashboard run
end to end.

Current priorities:

1. stabilise the Core-owned provider-neutral device and capability model;
2. add household roles, action policies, correlated audit and integration
   health above the working Nanoleaf reference integration;
3. introduce Home Assistant as an optional adapter with owner-selected Observe,
   Control or Manage access without making it the platform core;
4. prepare the authenticated Raspberry Pi gateway agent and verified backup,
   update and recovery foundations;
5. build Simple and Expert experiences only on the same authoritative state.

See the full [roadmap](docs/roadmap.md), the current
[development status](docs/status/README.md) and the single-file
[chat context snapshot](docs/status/CHAT-CONTEXT.md).

## Licence

No open-source licence has been selected yet.

Until a licence is explicitly added, all rights are reserved.

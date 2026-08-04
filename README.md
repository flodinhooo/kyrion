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

## Initial use case

The first Kyrion prototype will control an existing Nanoleaf installation
through its local network API.

The initial scope includes:

- discovering or configuring the Nanoleaf controller;
- reading the current device state;
- switching the panels on and off;
- changing brightness;
- displaying connection and API errors;
- providing a minimal web dashboard;
- supporting German and English user interfaces.

The first prototype does not require:

- a dedicated mobile application;
- a separate AI service;
- a database;
- Docker;
- user authentication;
- remote access.

These components will only be introduced when a real use case requires them.

## Planned architecture

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

During the first prototype, the web application may communicate with the
Nanoleaf local API through server-side Next.js functionality.

A dedicated Kyrion Core service will be introduced once multiple integrations,
users, permissions or complex workflows justify the additional separation.

Read the full [architecture documentation](docs/architecture.md).

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

The Kotlin and Spring Boot central backend. Its first implemented slice owns a
PostgreSQL-backed activity event log; permissions, devices, integrations,
commands and automations remain planned responsibilities.

`services/ai`

The planned optional AI service responsible for natural-language interpretation,
tool selection and summarisation.

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

Kyrion is currently in its foundation and working-prototype phase. The local
text-chat and browser-backed voice path runs end to end, Kotlin Core persists a
trusted activity log in PostgreSQL, and the identity/session security
foundation is prepared without exposing an unfinished login flow.

Current priorities:

1. retrieve a small relevant set of confirmed personal memories transparently;
2. add memory conflict, supersession and retention rules;
3. introduce controlled Core capability contracts and the first local device
   integration;
4. replace prototype browser speech providers where a suitable local voice
   stack is available.

See the full [roadmap](docs/roadmap.md) and the current
[development status](docs/status/README.md).

## Licence

No open-source licence has been selected yet.

Until a licence is explicitly added, all rights are reserved.

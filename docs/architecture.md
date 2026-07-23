# Kyrion Architecture

## Status

This document describes the intended high-level architecture of Kyrion.

Not every component described here exists in the initial version. Components
should only be implemented when they solve a concrete problem or support a real
use case.

The architecture is expected to evolve as the project grows.

## Architectural goals

Kyrion should be:

- local first;
- modular;
- secure by default;
- understandable;
- observable;
- multilingual;
- independent of individual manufacturers;
- usable without artificial intelligence;
- expandable without requiring a complete rewrite.

## System overview

Kyrion is planned as a modular platform consisting of user-facing applications,
a central core service, optional AI capabilities and external integrations.

```text
┌───────────────────────────────┐
│      User Interfaces          │
│                               │
│  Web Application             │
│  Mobile Application          │
│  Future Voice Interface      │
└───────────────┬───────────────┘
                │
                │ HTTP / JSON
                ▼
┌───────────────────────────────┐
│         Kyrion Core           │
│                               │
│  Authentication              │
│  Authorisation               │
│  Device management           │
│  Integration management      │
│  Command execution           │
│  Automation engine           │
│  Audit logging               │
│  Persistence                 │
└───────┬───────────────┬───────┘
        │               │
        │               │
        ▼               ▼
┌───────────────┐ ┌─────────────────┐
│ Integrations  │ │   AI Service    │
│               │ │                 │
│ Nanoleaf      │ │ Language        │
│ Jellyfin      │ │ Tool selection  │
│ Wake-on-LAN   │ │ Summarisation   │
│ Home Assistant│ │ Planning        │
│ Email         │ │ Speech          │
│ Calendar      │ │ Retrieval       │
└───────────────┘ └─────────────────┘
```

## Initial prototype architecture

The first Kyrion prototype intentionally uses a smaller architecture.

```text
Browser
   │
   ▼
Next.js Web Application
   │
   ▼
Server-side Nanoleaf Client
   │
   ▼
Nanoleaf Local API
   │
   ▼
Physical Nanoleaf Panels
```

The first prototype does not require:

- a dedicated core backend;
- a database;
- an AI service;
- a mobile application;
- Docker;
- authentication;
- external cloud infrastructure.

These components will be introduced only when the existing architecture no
longer supports the required functionality cleanly.

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

A monorepo allows related changes across the web application, backend,
integrations, AI service and documentation to be developed within one repository
and one Git history.

Each application or service still maintains its own language-specific build
configuration.

## Applications

### Web application

Planned technology:

- Next.js
- React
- TypeScript
- Tailwind CSS

Primary responsibilities:

- initial system setup;
- dashboard presentation;
- device control;
- device and integration configuration;
- room management;
- automation management;
- activity and error logs;
- text-based assistant interaction;
- language selection;
- administrative functionality.

The web application is the first user-facing application implemented by Kyrion.

### Mobile application

Planned technology:

- React Native
- Expo
- TypeScript

Primary responsibilities:

- quick device control;
- assistant interaction;
- status overview;
- notifications;
- language selection;
- later voice input;
- later device-native functionality.

The mobile application is not part of the first milestone.

It should only be introduced after the core user flows are validated in the web
application.

## Core service

Planned technology:

- Kotlin
- Spring Boot

Primary responsibilities:

- authentication;
- authorisation;
- user and household management;
- devices and rooms;
- integration lifecycle;
- command validation;
- command execution;
- automation orchestration;
- audit logging;
- persistence;
- communication with the AI service;
- communication with user-facing applications.

The core service becomes the authoritative source for platform state and
business rules.

### When should the core service be introduced?

A dedicated core service becomes justified when Kyrion requires one or more of
the following:

- multiple user-facing applications;
- multiple integrations;
- persistent device configuration;
- users and permissions;
- automation workflows;
- audit history;
- remote access;
- asynchronous command execution;
- AI tool execution;
- clear separation between UI and business logic.

Until then, the first prototype may use server-side Next.js functionality.

## AI service

Planned technology:

- Python
- FastAPI
- a local model runtime where practical
- optional external model providers

Primary responsibilities:

- natural-language interpretation;
- tool selection;
- structured command proposals;
- multi-step task planning;
- summarisation;
- optional speech-to-text processing;
- optional text-to-speech processing;
- optional semantic retrieval.

The AI service must not directly control devices, execute unrestricted operating
system commands or access external accounts without passing through Kyrion Core.

The intended flow is:

```text
User request
    │
    ▼
AI service interprets the request
    │
    ▼
AI service proposes a structured tool call
    │
    ▼
Kyrion Core validates permissions and arguments
    │
    ▼
Integration executes the command
    │
    ▼
Result is logged and returned to the user
```

Example tool proposal:

```json
{
  "tool": "light.setBrightness",
  "arguments": {
    "deviceId": "living-room-nanoleaf",
    "brightness": 30
  }
}
```

The AI service proposes actions. Kyrion Core remains responsible for deciding
whether an action is valid and permitted.

## Integrations

External systems are connected through integration adapters.

Possible integrations include:

- Nanoleaf;
- Wake-on-LAN;
- Home Assistant;
- Jellyfin;
- email providers;
- calendars;
- photovoltaic systems;
- routers;
- network services;
- smart lights;
- media systems;
- local file storage.

Each integration should expose capabilities through a common internal model.

Example capabilities:

```text
power.on
power.off
light.setBrightness
light.setColour
light.activateScene
computer.wake
media.play
media.pause
media.search
email.listUnread
calendar.listUpcoming
energy.getCurrentProduction
```

### Integration responsibilities

An integration adapter should be responsible for:

- connecting to the external system;
- handling authentication or local tokens;
- translating Kyrion commands into provider-specific requests;
- translating provider responses into Kyrion models;
- reporting connection errors;
- exposing supported capabilities;
- reporting device state where available.

### Integration boundaries

The web application should not need to understand manufacturer-specific APIs.

For example, the web application should request:

```text
light.setBrightness
```

It should not need to know whether the physical device is:

- Nanoleaf;
- Philips Hue;
- Shelly;
- another compatible lighting system.

Provider-specific behaviour belongs inside the integration adapter.

## Internationalisation

Kyrion supports German and English from the beginning.

Supported initial locales:

```text
de
en
```

English is the fallback locale.

### Technical language

English is the primary technical language for:

- source code;
- identifiers;
- API contracts;
- database field names;
- commit messages;
- technical documentation;
- developer-facing logs.

### User-facing language

All user-facing text must be translatable.

User-facing text includes:

- page headings;
- buttons;
- labels;
- navigation;
- validation messages;
- error messages;
- notifications;
- device capability names;
- automation descriptions;
- assistant responses generated from platform templates.

Visible text should not be hardcoded directly inside user-interface components.

Translations should be stored in dedicated locale resources.

Example structure:

```text
apps/web/
└── messages/
    ├── de.json
    └── en.json
```

Example translation keys:

```json
{
  "navigation.dashboard": "Dashboard",
  "devices.powerOn": "Einschalten",
  "devices.powerOff": "Ausschalten",
  "nanoleaf.brightness": "Helligkeit",
  "errors.deviceUnavailable": "Das Gerät ist nicht erreichbar."
}
```

The equivalent English file would use the same keys with English values.

### Locale persistence

The selected language should later be stored:

- per user, when user accounts exist;
- per installation, before user accounts exist;
- optionally through browser locale detection for the initial visit.

Manual user selection should override automatic detection.

### API error localisation

Backend services should return stable machine-readable error codes rather than
fully localised text.

Example:

```json
{
  "code": "DEVICE_UNAVAILABLE",
  "details": {
    "deviceId": "living-room-nanoleaf"
  }
}
```

The user-facing application translates the error code into the selected
language.

This prevents backend business logic from becoming coupled to a particular
language.

## API communication

Initial communication between components uses:

- HTTP;
- JSON;
- REST-style endpoints;
- typed request and response models.

OpenAPI should be introduced when multiple clients or services depend on the
same API contract.

Possible later additions include:

- Server-Sent Events for live status updates;
- WebSockets for interactive real-time communication;
- MQTT for IoT events;
- a message broker for durable asynchronous workflows.

These technologies should only be added when their advantages are required.

## Persistence

PostgreSQL is the preferred relational database once persistent state becomes
necessary.

Possible stored data includes:

- users;
- households;
- rooms;
- devices;
- integrations;
- credentials metadata;
- automations;
- execution history;
- language preferences;
- permissions;
- audit logs.

The first Nanoleaf prototype does not require a database.

Configuration can initially be provided through environment variables or a local
development configuration that is excluded from Git.

## Configuration and secrets

Secrets must never be committed to the repository.

Secrets include:

- API tokens;
- Nanoleaf authentication tokens;
- OAuth client secrets;
- encryption keys;
- database passwords;
- external service credentials.

Local development configuration may use environment variables.

Example:

```text
NANOLEAF_HOST=192.168.1.50
NANOLEAF_TOKEN=local-secret-token
```

An `.env.example` file may document required variable names without containing
real secret values.

Production deployments should use an appropriate secret-management mechanism.

## Security boundaries

Kyrion should follow these security rules:

- external credentials must be protected;
- AI-generated actions must be validated;
- destructive actions should require confirmation;
- integrations should receive only the permissions they require;
- user permissions should be checked by Kyrion Core;
- device-control endpoints must not be exposed directly to the public internet;
- remote access should use a secure mechanism such as a VPN;
- security-sensitive actions must be logged;
- secrets must not appear in logs;
- device input and provider responses must be treated as untrusted data.

## Observability

Kyrion should make system behaviour understandable.

Important events should be traceable, including:

- device commands;
- integration connection attempts;
- automation executions;
- failed actions;
- AI-proposed tool calls;
- user confirmations;
- configuration changes.

Logs should distinguish between:

- developer-facing technical information;
- user-facing activity history;
- security-relevant audit events.

## Deployment

### Initial development

The initial version runs directly on the developer's computer.

Services are started individually during development.

### Future always-on deployment

A later deployment may use an always-on mini PC running Linux.

Possible hosted components include:

- Kyrion Core;
- Kyrion Web;
- PostgreSQL;
- the AI service;
- Home Assistant;
- Jellyfin;
- monitoring;
- backup services.

### Containers

Docker may later be used to package and operate services consistently.

Docker is not required for the first prototype.

A container can only run while its host computer is powered on. Therefore,
always-on functions such as Wake-on-LAN require an always-on host such as a mini
PC, server or Raspberry Pi.

## First vertical slice

The first complete use case is Nanoleaf control.

```text
Kyrion Web
    │
    ▼
Nanoleaf server-side client
    │
    ▼
Nanoleaf local API
    │
    ▼
Nanoleaf controller and panels
```

Initial supported actions:

- configure the Nanoleaf controller address;
- authenticate against the local API;
- read the current state;
- switch the panels on;
- switch the panels off;
- change brightness;
- display meaningful errors;
- display the interface in German and English.

## First success criterion

The first milestone is complete when:

> A user can open Kyrion Web, select German or English and reliably control the
> existing Nanoleaf panels without using the official Nanoleaf application.

## Future architectural decisions

The following topics remain intentionally undecided:

- exact authentication solution;
- exact database access technology;
- exact local AI model runtime;
- exact mobile navigation architecture;
- exact plugin distribution format;
- exact remote-access solution;
- whether integrations run inside Kyrion Core or as separate processes;
- whether an event broker becomes necessary;
- whether the platform will later support third-party plugins.

These decisions should be documented through Architecture Decision Records when
they become relevant.

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

## Product architecture position

Kyrion is the trusted orchestration and operations layer, not a replacement for
every mature integration or protocol implementation. Core owns the stable
device model, household identity, permissions, policies, command decisions,
diagnostics, persistence and audit. Adapters supply connectivity and translate
external ecosystems into that model.

Home Assistant is an important optional adapter for integration breadth. Its
onboarding offers Observe, Control and Manage profiles backed by granular
Core-owned permissions. Home Assistant entity identifiers and service calls
never become Kyrion's public domain contract, and no arbitrary service call may
bypass Core policy even under Manage access. Native integrations remain
appropriate when they
prove Kyrion contracts, improve local reliability or diagnosis, support a
strategic capability, or are required by a managed gateway.

Material integration and device changes use a Core-orchestrated pre-change
restore point. One manifest records the applicable Core, provider, coordinator
and gateway backups plus coverage and restore-verification status. A created
backup is never presented as recoverable until its restore path has been
verified. See
[ADR 0006](adr/0006-integration-access-profiles-and-pre-change-restore-points.md).

The protected onboarding sequence is:

```text
Preflight and supported-backup discovery
                    |
                    v
Create restore-point manifest and component backups
                    |
                    v
Select access profile, household/device scope and confirmations
                    |
                    v
Inspect devices, rooms, provenance and duplicates
                    |
                    v
Owner approves import or migration plan
                    |
                    v
Apply through Core, validate result and append correlated audit events
```

The onboarding UI explains who may see the integration, which rooms and devices
are in scope, whether Velora may only explain or also propose supported actions,
and which actions require confirmation. Failed required protection blocks the
change. Partial or unsupported external backup coverage is identified precisely
and never represented as a complete rollback path.

See [Product Strategy](product-strategy.md) for the product-level rationale.

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
Kyrion Core resolves owner-visible targets and validates permissions,
capabilities, arguments and confirmation policy
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
whether an action is valid and permitted. Text chat and voice use the same
proposal contract. Core must reject unknown targets and request clarification
when a natural-language room or device selector matches zero or multiple
plausible targets rather than allowing the model to guess.

### Future AI deployment modes

The provider boundary should support three future deployment modes without
creating separate Kyrion products: models running on user-controlled hardware,
models hosted as an optional Kyrion-managed service, and owner-configured
external AI providers. STT, LLM and TTS are separate capabilities and may be
routed independently, so an installation can keep speech recognition local
while using a different provider for reasoning or voice synthesis.

Provider selection and hardware recommendations must be based on declared
capabilities and measured deployment profiles, not provider-specific branches
in Web, Core or the dialogue controller. Core remains local and authoritative
for identity, permissions, context release, action validation and audit in all
three modes. A remote AI request receives only the context required for that
request; connecting a cloud provider must not implicitly move durable
conversation history, personal memory, smart-home history or camera data into
that provider's storage.

External-provider credentials remain server-side. Data destination, expected
cost, retention implications and fallback behaviour must be visible before a
user enables remote processing. Managed or external AI is optional and must not
remove the essential non-AI or local control paths.

## Integrations

### Persistent device lifecycle invariant

Every connection method follows the same Core-owned lifecycle, including
Zigbee, Thread/Matter, Bluetooth, local-network discovery, Home Assistant and
future plugin adapters. Discovery produces an untrusted candidate. Once the
owner explicitly adds or approves that candidate, Core must create or update
one stable owner-scoped device record and the device must appear automatically
on `/home`; a provider adapter or browser-only list is not an inventory.

Core persists current owner-managed device metadata, including display name,
room assignment and enabled integration relationship. Creating, changing or
clearing a room assignment must update authoritative persistence before the UI
reports success. Reloading Web, restarting Core or temporarily losing a gateway
must not discard those choices. Provider observations such as availability,
power, brightness and colour remain timestamped observations rather than being
confused with owner configuration. Re-discovery reconciles the stable record;
it must not silently create duplicates or overwrite owner-managed metadata.

Web and mobile clients read this same Core inventory for Home. New adapters may
translate provider identities and capabilities, but they may not bypass this
lifecycle or maintain a separate authoritative device list.

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

Every provider-neutral device projection also exposes one of four availability
states:

- `online`: a sufficiently recent provider observation confirmed reachability;
- `offline`: a sufficiently recent provider observation confirmed the device
  was unreachable;
- `degraded`: the device is reachable but one or more expected functions are
  impaired;
- `unknown`: Kyrion has no sufficiently recent observation.

An availability value includes an observation timestamp when it is based on a
real check. `unknown` is not equivalent to `offline`, and Core must not invent a
timestamp or carry an old state forward without an explicit staleness policy.
Confirmed command execution is also a real observation: success records
`online`, confirmed provider unavailability records `offline`, and other
adapter failures record `degraded`. Failure to persist this secondary
observation must not rewrite a confirmed physical command as failed.

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

Provider-neutral command selectors may address either a room-wide group or one
stable owner-visible device identifier. Exactly one target form is accepted per
command. Core resolves the identifier within the authenticated owner scope and
never trusts the browser or AI service to establish ownership.

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

## Future extension architecture

Once the internal integration boundary is stable, Kyrion may expose it through
a versioned plugin framework. Plugins can add integrations or complete feature
modules without becoming part of Kyrion Core. Kyrion Core remains the trusted
control plane: it owns authentication, authorisation, command validation,
confirmation policies, persistence and audit logging.

The AI service may additionally load knowledge packages. These packages enrich
Velora with curated domain knowledge and tool descriptions, but they do not
bypass Core or execute actions directly. Personal knowledge remains separate
from shared packages and is scoped to the authorised user or household.

The detailed long-term model, including marketplace governance, product
editions and regulated domains, is documented in
[Marketplace and Enterprise Vision](marketplace-enterprise.md).

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

PostgreSQL is the implemented authoritative relational store. Flyway manages
identity, sessions, activity, conversations, personal memory, integration
connections, rooms, device assignments and bounded device observations.

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

Nanoleaf credentials are encrypted before persistence. The installation
encryption key remains separate from PostgreSQL as recorded in ADR 0005.

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
KYRION_DATABASE_PASSWORD=local-secret-password
KYRION_CREDENTIAL_KEY_FILE=E:/Kyrion/Data/secrets/credential.key
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

The first always-on gateway hardware has been selected and ordered: a
Raspberry Pi 5 (8 GB) with dedicated Zigbee and Thread radios. It has not yet
arrived or been validated. The Pi is intended to host radio-facing adapters,
OTBR and the first Velora voice satellite. The final placement of Core, Web,
PostgreSQL and the AI service remains to be validated separately.

Possible hosted components include:

- Kyrion Core;
- Kyrion Web;
- PostgreSQL;
- the AI service;
- Home Assistant;
- Jellyfin;
- monitoring;
- backup services.

See the [Development Hardware Roadmap](hardware-roadmap.md) for the ordered
equipment, target gateway boundary and validation plan.

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

Implemented actions:

- discover or manually configure the controller address;
- authorise an owner-specific local API token;
- read the current state;
- switch the panels on and off;
- change brightness;
- change colour and colour temperature;
- list and activate controller-stored scenes;
- organise persistent devices into owner-specific rooms;
- display meaningful errors;
- display the interface in German and English.

## First success criterion

The first milestone success criterion has been reached:

> A user can open Kyrion Web, select German or English and reliably control the
> existing Nanoleaf panels without using the official Nanoleaf application.

## Future architectural decisions

The following topics remain intentionally undecided:

- exact mobile navigation architecture;
- exact plugin distribution format;
- exact remote-access solution;
- how future third-party integrations are isolated from Core;
- whether an event broker becomes necessary;
- the exact trust and isolation model for third-party plugins.

These decisions should be documented through Architecture Decision Records when
they become relevant.

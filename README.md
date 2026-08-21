<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/logo/kyrion-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="branding/logo/kyrion-light.svg">
    <img alt="Kyrion" src="branding/logo/kyrion-light.svg" width="560">
  </picture>
</p>

# Kyrion

> A local-first orchestration platform for devices, services, automations and
> optional AI.

Kyrion is being developed as an open-source project. It explores how a
personal digital environment can connect smart-home devices, local services,
media, knowledge and AI without giving an AI model direct authority over the
user's systems.

The project is currently a working development prototype, not a finished
consumer product. Its implemented vertical slices run on real local hardware;
planned capabilities are documented separately and are not presented as
complete.

> **Licence notice:** the source is being prepared for open-source publication,
> but a repository licence has not yet been selected. Until a `LICENSE` file is
> added, the code remains all rights reserved and cannot yet be reused under an
> open-source licence.

## Why Kyrion exists

Personal infrastructure is fragmented across vendor applications, cloud
accounts and incompatible ecosystems. Kyrion aims to provide one coherent,
auditable layer above them while preserving a few non-negotiable boundaries:

- essential functions remain usable without AI;
- local processing and storage are preferred where practical;
- external providers are optional and visible;
- Core, not an LLM, owns permissions and execution decisions;
- integrations expose stable capabilities instead of leaking vendor APIs;
- important actions are validated, correlated and recorded;
- German and English are supported from the beginning.

The guiding rule for AI-assisted actions is:

> **LLM proposes. Core decides. Adapter executes. Result confirms.**

Read the [project vision](docs/vision.md), [principles](docs/principles.md) and
[product strategy](docs/product-strategy.md) for the longer-term direction.

## What works today

The current local development installation includes the following implemented
slices.

### Platform and security

- local owner setup and authentication;
- Argon2id password hashing and opaque, hashed session credentials;
- owner-scoped PostgreSQL persistence;
- conversation history and deterministic context compaction;
- explicit, owner-controlled personal memory;
- an append-only activity log with correlation identifiers;
- German and English Web interfaces.

### Devices and integrations

- local Nanoleaf discovery, physical authorisation and encrypted credentials;
- Nanoleaf state, power, brightness, colour, temperature and stored scenes;
- persistent rooms, device names and room assignments;
- a provider-neutral device catalog and bounded command contracts;
- an authenticated Raspberry Pi 5 gateway agent;
- Zigbee discovery and explicit approval through Zigbee2MQTT;
- physical control of two Philips Hue colour lamps through the shared Core
  command path;
- explicit `online`, `offline`, `degraded` and `unknown` availability.

### AI and voice

- local streaming chat through a provider-neutral AI service and Ollama;
- bounded German and English device-command proposals;
- a Raspberry Pi Voice Satellite with local `Hey Velora` wake-word inference;
- local VAD, microphone capture and provider-neutral Parakeet transcription;
- authenticated, Core-owned multi-turn voice sessions;
- Bluetooth/PipeWire playback through physical speakers;
- provider-neutral Fixed, Template and Dynamic voice-response plans;
- checksum-pinned reviewed-audio support and an owner-scoped template cache.

The Voice Satellite can already complete ordinary local batch conversations.
The next MVP milestone connects it to the same Core-owned action path used by
Web and returns spoken success only after a real adapter result.

## Current focus

Development is deliberately focused on a small, useful Voice MVP rather than
continued general TTS experimentation:

1. produce the first reviewed Velora fixed-response assets using local recording
   and offline voice conversion;
2. move command orchestration out of the Next.js chat route into Kyrion Core;
3. add minimal room categories for natural and deterministic target resolution;
4. prove one German Nanoleaf power command through the physical Voice Satellite;
5. repeat the path at least twenty times and test timeout, offline, ambiguity
   and stale-session failures;
6. expand through the same contracts to Zigbee, Thread/Matter and local Wi-Fi
   devices.

The detailed sequence is captured in the
[Voice and Action MVP plan](docs/status/2026-08-12-voice-action-mvp-plan.md) and
its [dated TODO checkpoint](docs/status/2026-08-12-voice-action-mvp-todo.md).

## Architecture

```text
Web / Voice Satellite / future Mobile / Automations
                         |
                         v
                    Kyrion Core
       identity | policy | persistence | audit
            target resolution | action decisions
                  /                    \
                 v                      v
       Integration adapters       Optional AI service
       Nanoleaf / Zigbee / ...    STT / proposals / chat / TTS
```

Component ownership is intentional:

- **Web** presents state and collects intent through same-origin routes. It does
  not own provider rules or browser-visible secrets.
- **Kyrion Core** is the Kotlin/Spring Boot authority for authentication,
  ownership, permissions, policy, target resolution, command execution,
  persistence and audit.
- **AI service** is a Python/FastAPI capability provider for language,
  transcription and speech. Its proposals are untrusted until Core validates
  them.
- **Gateway agent** performs only bounded operations authorised by Core and
  reports typed health and device observations.
- **Voice Satellite** owns local wake detection, bounded capture and playback.
  It cannot execute device actions directly.
- **Adapters** translate Kyrion capabilities into provider-specific APIs.
  Home Assistant may later be one optional adapter; it is not the platform
  core.

See [Architecture](docs/architecture.md) and the accepted
[Architecture Decision Records](docs/adr/) for detailed boundaries.

## Repository layout

```text
kyrion/
|-- apps/
|   |-- web/                 Next.js and React Web application
|   `-- mobile/              planned Expo application
|-- services/
|   |-- core/                Kotlin/Spring Boot authority
|   |-- ai/                  Python/FastAPI AI and speech capabilities
|   |-- gateway-agent/       bounded Raspberry Pi gateway runtime
|   `-- voice-satellite/     local wake, capture and playback runtime
|-- packages/
|   `-- api-contracts/       shared/generated contracts scaffold
|-- infrastructure/         local deployment and node configuration
|-- docs/                    architecture, roadmap, ADRs and evidence
`-- README.md
```

## Technology

- Next.js, React and TypeScript;
- Kotlin, Spring Boot and Gradle;
- Python, FastAPI and Pydantic;
- PostgreSQL and Flyway;
- Ollama for replaceable local language-model execution;
- NVIDIA Parakeet behind a provider-neutral local HTTP boundary for speech recognition;
- openWakeWord and ONNX on the Raspberry Pi;
- Zigbee2MQTT and loopback-only Mosquitto for the current Zigbee adapter;
- PipeWire, ALSA and Bluetooth for the Voice Satellite audio path.

Speech runtimes, model weights, private recordings and device credentials are
not treated as ordinary repository assets. Their versions, licences and local
storage boundaries must be reviewed separately.

## Development status and evidence

Kyrion distinguishes four states explicitly:

- **implemented**: present in the repository with proportionate tests;
- **physically verified**: exercised against the documented local hardware;
- **experimental**: isolated code or benchmarks that are not active product
  paths;
- **planned**: architectural direction or roadmap scope not yet implemented.

Useful starting points:

- [Current development status](docs/status/README.md)
- [Current TODO](docs/status/TODO.md)
- [Project roadmap](docs/roadmap.md)
- [Single-file context snapshot](docs/status/CHAT-CONTEXT.md)
- [Development startup](docs/development-startup.md)
- [Hardware roadmap](docs/hardware-roadmap.md)

Several voice-provider and streaming experiments remain in the repository as
reproducible evidence. They are not automatically installed, started or
considered production dependencies.

## Running the project

Kyrion is not yet packaged for one-command consumer installation. Local
development currently requires the Web application, Core, AI service,
PostgreSQL and selected local providers to be configured independently.

Start with [Local Development Startup](docs/development-startup.md). Hardware
integrations additionally require owner-controlled devices, private local
configuration and explicit enrolment. Never commit credentials, model caches,
private recordings or generated training data.

## Roadmap direction

Near-term work focuses on trustworthy orchestration and real hardware:

- shared Core Action Orchestrator for Web, Voice and later clients;
- typed policy and confirmation classes;
- natural room resolution using visible names and room categories;
- Voice-confirmed Nanoleaf and Zigbee actions;
- Home Assistant Connect ZBT-2, Thread/Matter and local Wi-Fi validation;
- gateway recovery, backup and restore verification.

Later domains may include calendar, email, local file search, Spotify, YouTube,
playback routing and automations. These will use domain-specific typed actions
above the same Core authority rather than being added as unrestricted AI tools.

The Web experience will also be reconsidered as a personal local platform
rather than remaining centred on a generic chat interface.

## Contributing

External contribution guidance, issue templates and a code of conduct have not
yet been published. Until those are added, the repository should be considered
an actively developed project shared for transparency and portfolio review.

Architecture and implementation contributions must preserve the boundaries in
[AGENTS.md](AGENTS.md): Core authority, least privilege, provider-neutral
contracts, German/English parity, local-first operation and explicit separation
between implemented and planned functionality.

## Licence

Kyrion is intended to be released as open source, but the licence decision is
still pending. Until a `LICENSE` file is committed, all rights are reserved.
Do not assume permission to copy, modify or redistribute the source yet.

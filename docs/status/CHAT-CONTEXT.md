# Kyrion Chat Context Snapshot

Snapshot: 2026-08-12, repository baseline `3a80ba1`.

Use this as the single starting context for a new development chat. It
distinguishes implemented, physically verified, experimental and planned work.
It does not replace `AGENTS.md`, ADRs or the linked evidence reports.

## Ready-to-use new-chat prompt

> Work in the Kyrion repository. Read `AGENTS.md`, `README.md` and
> `docs/status/CHAT-CONTEXT.md`, then inspect the current worktree and relevant
> code. Core remains authoritative for identity, policy, persistence, device
> commands and audit. Preserve local-first operation, German/English parity and
> unrelated changes. Do not treat experiments or plans as implemented. Task: ...

## Product and architecture

Kyrion is a local-first, modular and auditable platform for devices, services,
media, automations and optional AI. Velora is the current assistant identity,
not a platform dependency.

- Web presents state and intent through same-origin Next.js routes. It owns no
  provider rules or secrets.
- Kotlin/Spring Boot Core owns authentication, authorisation, business rules,
  PostgreSQL persistence, permissions, command validation/execution and audit.
- Python/FastAPI AI interprets language and proposes typed actions. It never
  directly controls devices, accounts or unrestricted OS commands.
- Integrations map provider APIs into stable Kyrion capabilities and cannot
  bypass Core. Credentials remain server-side.
- German and English ship together. English is the technical/documentation
  language.
- Home Assistant is a future optional adapter, not Core. Ollama and speech
  runtimes are replaceable providers.

Implemented components are `apps/web`, `services/core`, `services/ai`,
`services/gateway-agent`, `services/voice-satellite` and PostgreSQL/local-node
infrastructure. `apps/mobile` and shared generated API contracts are not built
out beyond scaffolding.

## Implemented product behaviour

### Identity, chat, persistence and memory

- One-time local-owner setup, login, current user, password change and logout.
- Argon2id passwords; opaque 256-bit sessions; only SHA-256 token hashes stored.
- `HttpOnly`, `SameSite=Strict` cookie plus double-submit CSRF protection.
- Owner-scoped conversations and ordered messages. User turns are saved before
  model invocation; complete or visibly stopped trusted output is persisted.
- Deterministic Core-owned context compaction and turn lifecycle.
- Explicit owner-controlled personal memory with confirmation, conflicts,
  settings, retrieval and deletion. Semantic retrieval/expiry remain open.
- Streaming local chat through Next.js, FastAPI and deployment-selected Ollama
  models. Activity, Conversations, Profile and model settings are implemented;
  Automations and Knowledge remain placeholders.
- Append-only activity events with correlation IDs and a data-minimised Web
  view. Actor ownership, retention and tamper evidence remain open.

### Nanoleaf reference integration and Home

- Explicit mDNS discovery with private-IPv4 fallback, physical authorisation,
  per-owner connections and AES-GCM-encrypted credentials.
- State, power, brightness, colour, colour temperature, stored scenes and
  palette previews.
- Editable persistent names, confirmed removal, rooms and assignments.
- Bilingual Plugins and Home views with room/device cards, state, quick actions
  and detailed controls.
- Bounded observation refresh for at most 20 connections. Availability is
  `online`, `offline`, `degraded` or `unknown` with timestamps; state older than
  60 seconds is reported honestly as unknown.
- Commands update observations without letting an observation-storage failure
  falsify a successful physical action.
- DHCP reconciliation and physical controller-token revocation remain open.

### Typed Velora device commands

- AI receives only a bounded owner catalog: stable ID, provider, name, room,
  capabilities and availability—never hosts or credentials.
- Explicit German/English power and brightness imperatives can target all
  compatible Nanoleafs in an exact room or one exact, unique device name.
- `room`/`raum` aliases and immediate contextual room correction are accepted
  only when resolution is unique and capability-compatible.
- Partial, duplicate, invented and incompatible targets are rejected. Core
  resolves and revalidates the proposal, executes the existing adapter path and
  returns a deterministic response from the confirmed result/correlation ID.
- Natural-language colours, scenes, pronouns and clarification turns remain
  open.

### Gateway, discovery and Zigbee

- Authenticated Raspberry Pi gateway registration, five-second heartbeat,
  persisted health and 45-second offline threshold with a bilingual Web view.
- Discovery is not authority. Zigbee candidates require an explicit owner name
  and Add action before Core creates/reconciles a stable record.
- Approved Nanoleaf and Zigbee devices share the persistent Home/catalog/room
  experience.
- Hue power, brightness, hue, saturation and colour-temperature state/actions
  use typed Core contracts.
- Web actions use a persisted audited async queue; command polling is 250 ms,
  health remains five seconds, and pending/success/failure is visible.
- Confirmed removal succeeds in Zigbee2MQTT before Core deletes the device.
  Supported Hue Add also configures recover-last-state power-on behaviour.
- Retry, timeout and idempotency hardening remain open.

## Physically verified hardware

- Raspberry Pi 5 (8 GB) registered as `kyrion-node`; host, storage, Ethernet,
  IPv6, temperature, throttling inventory and agent restart validated.
- Sonoff ZBDongle-E as Ember coordinator behind loopback-only MQTT/Zigbee2MQTT.
- Two Philips Hue LCA011 lamps paired, explicitly approved/named, controlled
  from Web, persistently assigned and cold-power recovery configured.
- Delock USB microphone capture and Pebble V3 Bluetooth/PipeWire playback,
  default sink and reboot reconnect passed.
- Full Pi reboot heartbeat recovery and temporary network-loss recovery remain
  to be recorded. Home Assistant Connect ZBT-2 is not accepted. Matter/Thread,
  general Bluetooth and Wi-Fi integrations are not accepted merely from
  discovery.

## Voice implementation and decisions

- Browser Voice Mode uses the authenticated chat/command path but still relies
  on browser speech APIs; complete hands-free barge-in is not implemented.
- A non-privileged Pi service performs local openWakeWord inference for
  `Hey Velora`. The deployed second candidate improved small tests but remains
  a test candidate needing broader physical evaluation.
- Authenticated post-wake PCM16 uplink, synthetic 160 ms downlink,
  cancellation/reconnect, bounded jitter buffering and raw PipeWire playback
  passed automated and physical checks. Clean playback uses a 320 ms prebuffer.
- Core owns authenticated voice sessions and typed Fixed/Template/Dynamic plans
  (ADR 0010). Live batch dialogue requests a greeting, acknowledges valid
  non-terminal STT, synthesises dynamic dialogue and closes on deterministic
  farewell intent.
- Fixed audio is checksum-pinned in a manifest. Templates use trusted slots and
  an owner-isolated complete-utterance WAV cache. Misses and dynamic answers use
  the provider-neutral normal batch fallback.
- Twelve DE/EN greeting/farewell/acknowledgement WAVs are specified but not yet
  owner-created, listened to or approved; the manifest marks them pending.
- A first XTTS-generated review batch exists outside Git: eight candidates were
  rejected, four remain unreviewed, none was accepted or registered. Do not
  trim, repair, register or regenerate these as an implicit Short-TTS experiment.
  A curated sound-engineering comparison package also exists outside Git; the
  immediate continuation is to agree the performance/recording approach and
  create twelve high-quality reviewed recordings.
- Command success/failure templates exist, but live Pi voice does not yet speak
  them because the controller does not receive the actual Core command result
  and correlation ID. It must never infer success from model text or introduce
  a second execution path.
- Adaptive voice answers allow concise two-to-four-sentence responses, prior
  claim correction and a 256-token safety ceiling; physical before/after
  acceptance is still open.

Provider conclusions:

- Faster-Whisper `small/int8` remains bounded final-STT baseline; rolling
  streaming failed latency.
- Nemotron 3.5 CPU Q8 did not clearly beat the quality gate and is frozen no-go.
- Qwen 1.7B streaming mapped/cancelled correctly but failed latency/continuity.
- CosyVoice failed its cheap streaming gate.
- Chatterbox remains the working local batch fallback behind neutral
  `http_batch` configuration.
- XTTS v2 is experimental/opt-in for normal/longer output. Reproducible fantasy
  speech after short German text defeated EOS, tokenisation, VAD, guard and
  conditioning experiments; dynamic Short optimisation is closed.
- Accepted MVP direction: reviewed fixed audio, cached complete templates and
  normal provider-neutral TTS for dynamic text. No Short-TTS provider selected.

## Last recorded verification

- Web lint and production build passed.
- AI Ruff passed; stable Voice MVP recorded 91 passing AI tests.
- Voice Satellite Ruff passed; 47 tests passed.
- Core voice selection and `bootJar` passed.
- Full Core run: 56/57; the remaining Testcontainers test could not initialise
  without Docker and did not fail an application assertion.
- Isolated PostgreSQL checks passed setup, auth, password rotation and owner
  isolation. Physical Nanoleaf, gateway, Hue, audio and PCM evidence is above.

These results predate future changes; rerun proportionate checks after edits.

## Accepted direction, not implemented yet

- Stabilise provider-neutral device/state/capability/command/result contracts
  and centralise target resolution in a Core-owned Device Manager.
- Add households, owner/member/guest roles, action risk/confirmation classes,
  granular permissions and understandable Observe/Control/Manage presets.
- Extend correlated audit and integration-health reason explanations.
- Add Home Assistant only as a bounded adapter over Kyrion contracts.
- Add visible pre-change restore-point coverage and separate restore validation
  before material onboarding, elevation, pairing or migration.
- Productise gateway onboarding without SSH only after protocol/recovery slices.
- Build Simple and Expert modes over the same authoritative state.

## Immediate open checkpoints

1. Discuss the curated examples with the sound engineer, then create,
   listen-review and register the twelve fixed Velora WAVs one by one.
2. Run physical DE/EN Pi stable-Voice-MVP acceptance.
3. Connect spoken command templates only to real Core results/correlation IDs.
4. Repeat physical DE/EN text, brightness and browser Voice commands; verify
   explicit refresh and truthful unavailable-controller feedback.
5. Harden async Zigbee failure boundaries and tests.
6. Record Pi reboot/network-loss recovery and validate ZBT-2.
7. Continue Device Manager, permissions, audit and health before integration
   breadth.

## Detailed source of truth

- [Architecture](../architecture.md), [product strategy](../product-strategy.md),
  [roadmap](../roadmap.md), [cumulative status](README.md), [task list](TODO.md)
  and [startup guide](../development-startup.md).
- [Stable Voice MVP](2026-08-11-stable-voice-mvp.md),
  [canonical Voice MVP handoff](2026-08-12-voice-mvp-handoff.md),
  [deterministic voice responses](2026-08-11-deterministic-voice-response-slice.md),
  [streaming closeout](2026-08-10-qwen-streaming-closeout.md) and
  [wake-word report](2026-08-09-voice-satellite-wake-word.md).
- [Gateway architecture](../gateway/architecture.md),
  [hardware roadmap](../hardware-roadmap.md), [ADR 0008](../adr/0008-core-owned-multiturn-voice-sessions.md),
  [ADR 0009](../adr/0009-local-provider-neutral-streaming-voice-pipeline.md) and
  [ADR 0010](../adr/0010-core-owned-typed-voice-response-plans.md).

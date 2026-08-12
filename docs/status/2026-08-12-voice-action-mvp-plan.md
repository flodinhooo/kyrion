# Voice and Action MVP plan

Date: 2026-08-12

## Objective

Build the smallest reliable Kyrion Voice MVP that understands a German room
command, resolves the target semantically, executes one real Nanoleaf action
through Core and speaks only a result justified by the authoritative execution
outcome.

The immediate target is:

```text
Hey Velora
  -> local wake word and bounded capture
  -> Faster-Whisper transcript
  -> typed action proposal
  -> Core validation and room resolution
  -> Nanoleaf power command
  -> confirmed DeviceCommandResult
  -> reviewed fixed Velora response
```

This plan supersedes further general TTS discovery in the Voice MVP lane. It
does not reopen the closed Short-TTS or XTTS termination experiments.

## Non-goals

- building or training a final Velora TTS engine;
- integrating voice conversion into the Kyrion runtime;
- enabling unrestricted LLM tool execution;
- implementing every planned action domain;
- adding a large room ontology or free-form alias system immediately;
- redesigning the Web application during the Voice MVP;
- enabling experimental streaming components on the Raspberry Pi.

## Accepted principles

1. **LLM proposes. Core decides. Adapter executes. Result confirms.**
2. Fixed responses use reviewed, versioned audio assets.
3. Template responses use trusted Core slots and the existing complete-utterance
   cache.
4. Dynamic responses retain the replaceable normal batch-TTS path.
5. Positive command speech is impossible before a real successful result.
6. Web, Voice, future Mobile and Automations use the same Core action path.
7. Smart Home is the first action domain, not the shape of the entire action
   architecture.
8. Voice conversion is an external offline production tool only.

## Current baseline

Implemented and preserved:

- Core-owned authenticated Voice Satellite sessions;
- local wake word, VAD, bounded WAV capture and PipeWire playback;
- local Faster-Whisper transcription with explicit locale;
- provider-neutral Fixed, Template and Dynamic response plans;
- checksum-pinned fixed-asset manifest and registration tool;
- owner-scoped complete-utterance template cache;
- Core `DeviceCommandService` with Nanoleaf and Zigbee execution;
- `DeviceCommandResult` with per-target outcomes and correlation ID;
- Web text-command flow through the Next.js chat route.

Known gaps:

- no approved fixed-response production WAVs;
- Web still owns proposal orchestration and result wording;
- Voice does not execute through the authoritative command path;
- room resolution is based mainly on exact names;
- `Room` has no semantic category;
- permission, policy and confirmation decisions are not yet a unified action
  layer;
- automatic `dialogue.acknowledged` speech currently occurs before ordinary
  non-terminal turn processing and must not imply command success.

## Phase A: fixed Voice assets

### Production toolchain

Use an external Windows workflow:

```text
Audacity recording
  -> selected and cleaned source take
  -> Seed-VC offline conversion
  -> conservative mastering
  -> blind listening review
  -> mono PCM16 24 kHz WAV
  -> Kyrion registration tool
```

Audacity is the primary recorder/editor. Preserve raw sessions outside Git and
never overwrite them. Seed-VC is the first conversion candidate because its
zero-shot offline path can use a short target reference without first training
a dedicated voice model. RVC remains a follow-up only if a legally usable,
consistent target dataset of sufficient duration becomes available.

Recommended private storage:

```text
E:/Kyrion/Data/voice-production/velora-mvp-v1/
  01-raw-sessions/
  02-selected-takes/
  03-clean-source/
  04-converted-seed-vc/
  05-mastered-candidates/
  06-blind-review/
  07-approved/
  metadata/
```

Final assets must be complete mono RIFF/WAV, PCM16, 24 kHz and owner-approved.
No rejected or partially reviewed candidate enters the manifest.

### Initial 28-asset catalog

Frequent identity-bearing responses have two variants per locale. Less frequent
errors begin with one variant per locale.

| Response key | German | English | Mode and authority |
| --- | --- | --- | --- |
| `session.greeting` | `Hallo.` / `Hallo, schön dich zu hören.` | `Hello.` / `Hello, good to hear you.` | Fixed; active session |
| `session.farewell` | `Bis später.` / `Mach's gut.` | `Talk to you later.` / `Take care.` | Fixed; session ending |
| `dialogue.acknowledged` | `Okay.` / `Alles klar.` | `Okay.` / `Got it.` | Fixed; never command success |
| `command.succeeded` | `Erledigt.` / `Ist erledigt.` | `Done.` / `It's done.` | Fixed; confirmed complete success only |
| `command.failed` | `Das hat nicht funktioniert.` / `Der Befehl ist fehlgeschlagen.` | `That didn't work.` / `The command failed.` | Fixed; confirmed failure only |
| `target.not_found` | `Ich konnte das Ziel nicht finden.` | `I couldn't find that target.` | Fixed; Core resolution |
| `target.ambiguous` | `Das Ziel ist nicht eindeutig.` | `That target is ambiguous.` | Fixed; Core resolution |
| `device.offline` | `Das Gerät ist momentan nicht erreichbar.` | `The device is currently unavailable.` | Fixed; adapter/result state |
| `action.denied` | `Diese Aktion ist nicht erlaubt.` | `That action isn't allowed.` | Fixed; Core policy |

Target-specific, counted or partially successful results remain templates, for
example `command.succeeded.detail` and `command.partially_succeeded`. Arbitrary
dialogue remains Dynamic.

### Listening gate

Every candidate is reviewed for:

- exact words and language;
- clean ending with no invented continuation;
- stable Velora identity;
- natural short-sentence prosody;
- consonants, sibilance and plosives;
- consistent perceived loudness;
- no clipping, excessive denoising or conversion artifacts;
- suitable leading and trailing silence.

## Phase B: Core Action architecture

### Minimal extensible model

Add a thin action layer above existing domain services:

```text
ActionRequest
  -> ProposalProvider
  -> typed ActionProposal
  -> domain ActionHandler
  -> target and capability validation
  -> ActionPolicyService
  -> optional confirmation
  -> domain execution service
  -> ActionOutcome
```

The first typed proposal is `DeviceActionProposal`. Future proposal types may
include Calendar, Email, Local Search, Spotify, YouTube, Playback and
Automation without weakening Core authority or sharing untyped payloads.

Initial policy classes:

- `read`;
- `routine`;
- `confirmation_required`;
- `restricted`;
- `forbidden`.

The action context records owner, actor, interaction channel, locale, session
or conversation scope and correlation ID. Voice is an explicit channel that a
policy may allow or deny.

### Smallest refactoring

1. Add a Core-owned `ActionOrchestrator` and typed contracts.
2. Add `DeviceActionHandler`, delegating final execution to the existing
   `DeviceCommandService`.
3. Let Core build the owner-scoped device catalog and request a bounded proposal
   from the AI service.
4. Validate the returned proposal again in Core.
5. Return one stable `ActionOutcome` with safe facts and error code.
6. Expose a Core action endpoint for Web.
7. Replace proposal, execution and result wording in the Next.js route with a
   call to that endpoint.
8. Let `VoiceDialogueService` invoke the same orchestrator directly after STT.
9. Resolve the authoritative outcome through `VoiceResponsePolicyRegistry`.

Next.js retains browser authentication, CSRF, same-origin proxying and response
streaming. It stops owning device catalogs, proposal validation, execution and
command-result wording.

## Minimal Room category slice

Add `roomType` as a stable lowercase string validated against a Core enum. Use
`other` as the migration default. Do not use a database enum.

Initial values:

```text
living_room, office, study, bedroom, children_room, guest_room,
hobby_room, gaming_room, kitchen, dining_room, bathroom, toilet,
hallway, entrance, storage, basement, laundry_room, garage, workshop,
balcony, terrace, garden, other
```

Resolution priority:

1. exact visible room name;
2. later explicit owner alias;
3. unique localized synonym for `roomType`;
4. ambiguous result;
5. not-found result.

Examples:

```text
displayName: Setup
roomType: office

"im Büro" -> Setup, only if exactly one owner room has type office
```

Aliases are a later separate owner-scoped table. They are not stored as an
unchecked JSON array in the first migration.

## Phase C: first physical Nanoleaf command

Scope:

- German only;
- `power.set` only;
- Nanoleaf only;
- one unambiguous room;
- room resolution by visible name or `roomType` synonym;
- no clarification dialogue yet.

Required flow:

```text
Wake Word
  -> VAD/capture
  -> de transcript
  -> DeviceActionProposal
  -> Core owner/target/capability/argument/policy checks
  -> Nanoleaf adapter
  -> DeviceCommandResult
  -> ActionOutcome
  -> fixed command.succeeded or truthful failure response
  -> one Satellite playback
```

`dialogue.acknowledged` is not played before command execution. A neutral earcon
may later indicate processing but must not imply success.

## Phase D: reliability gate

Run at least twenty physical repetitions. Each turn carries session ID, turn
ID, proposal identity and one correlation ID.

Reject the slice on any occurrence of:

- more than one adapter execution for a turn;
- more than one result playback;
- success speech without complete confirmed success;
- execution or audio from an old/cancelled turn;
- execution after session closure;
- success after timeout;
- success after adapter failure;
- silent coercion of ambiguous or unknown targets.

After the repeated success path, test offline, timeout, not found, ambiguous,
adapter failure and inactive-session boundaries.

## Phase E: hardware and integration order

1. Complete Nanoleaf Voice and failure acceptance.
2. Reuse the action path for existing Zigbee Hue lights.
3. Harden asynchronous Zigbee timeout, retry and idempotency handling.
4. Add the Sonoff button and motion sensor as typed event slices.
5. Validate Home Assistant Connect ZBT-2 as a dedicated Thread radio.
6. Establish and recover OTBR/Thread state.
7. Add the Aqara P2 contact sensor as the first Matter-over-Thread event slice.
8. Add Shelly H&T Gen3 temperature/humidity observations.
9. Add myStrom WiFi Switch 2 power and energy capabilities.
10. Treat Bluetooth discovery and access as a separate bounded slice.

Home Assistant may be added later as an optional adapter with Observe, Control
and Manage profiles. It does not become Kyrion Core or a mandatory runtime.

## Raspberry Pi MVP runtime

Required:

- `kyrion-voice-satellite`;
- `kyrion-gateway-agent`;
- `zigbee2mqtt` and loopback-only `mosquitto` while Zigbee remains active;
- ALSA capture, PipeWire, WirePlumber and Bluetooth playback;
- networking, time synchronisation, system logging and current development SSH.

No experimental TTS, streaming-TTS or PCM debug server currently runs on the
Pi. Prototype modules remain available in the repository but are not active
runtime services.

Candidates for a separate reversible headless-node cleanup include AnyDesk,
the graphical desktop/display manager, CUPS, unused NFS/RPC services, desktop
portals and MPRIS. `filter-chain`, PipeWire, WirePlumber and Bluetooth must not
be disabled before proving that Pebble playback still works. Disable services,
do not uninstall them, and document rollback plus a reboot acceptance run.

## Deferred product work

- final custom Velora TTS or speaker dataset;
- streaming TTS and barge-in;
- free-form room aliases and clarification dialogue;
- additional Action domains beyond the contracts required by Device actions;
- broad Home Assistant onboarding;
- full Web information-architecture redesign.

The later Web redesign should present Kyrion as a personal local platform for
home, services, data and automations rather than centering the product on a
generic chat surface.

## Primary implementation files for the next code phase

Existing files likely to change:

- `apps/web/src/app/api/chat/route.ts`;
- `services/core/src/main/kotlin/dev/kyrion/core/capability/DeviceCommand.kt`;
- `services/core/src/main/kotlin/dev/kyrion/core/capability/DeviceCatalog.kt`;
- `services/core/src/main/kotlin/dev/kyrion/core/home/Room.kt`;
- `services/core/src/main/kotlin/dev/kyrion/core/home/JdbcRoomRepository.kt`;
- `services/core/src/main/kotlin/dev/kyrion/core/home/RoomController.kt`;
- `services/core/src/main/kotlin/dev/kyrion/core/voice/VoiceDialogueController.kt`;
- `services/core/src/main/kotlin/dev/kyrion/core/voice/VoiceResponsePlan.kt`;
- `services/ai/src/kyrion_ai/contracts.py`;
- `services/ai/src/kyrion_ai/device_commands.py`;
- `services/ai/voice-responses/manifest.json`;
- `apps/web/src/features/home/contracts.ts`;
- `apps/web/src/features/devices/contracts.ts`;
- `apps/web/src/app/(workspace)/home/page.tsx`;
- applicable German and English locale resources and tests.

Expected new files include a Core action package, a Flyway room-type migration,
focused action/target-resolution tests and an ADR for the shared Core Action
Orchestrator before implementation.

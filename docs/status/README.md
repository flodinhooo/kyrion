# Kyrion Development Status

Last updated: 2026-08-06

This directory is the durable handoff point for continuing development in a
new chat or work session. Read this file together with the root `AGENTS.md`,
`README.md` and the relevant architecture documents before changing code.

## Current vertical slices

The local text and voice path is implemented:

```text
Browser on http://localhost:3000
    |
    v
Next.js POST /api/chat
    |
    v
Kyrion AI Service on http://127.0.0.1:8000
    |
    v
Ollama on http://127.0.0.1:11434
    |
    v
Configured local model
```

The first trusted Core persistence path is also implemented:

```text
Browser /activity
    |
    v
Next.js GET /api/activity
    |
    v
Kyrion Core GET /v1/activity
    |
    v
PostgreSQL on E:\Kyrion\Data\postgres
```

Protected owner-scoped conversations are implemented as well:

```text
Authenticated browser
    |
    v
Next.js same-origin session and CSRF boundary
    |
    v
Kyrion Core owner validation
    |
    v
PostgreSQL conversations and ordered messages
```

The first owner-scoped integration slice is implemented:

```text
Authenticated browser /plugins/nanoleaf
    |
    v
Kyrion Core validation, confirmation and activity audit
    |
    v
Encrypted per-owner credential + Nanoleaf local OpenAPI
```

The persistent home dashboard is implemented:

```text
Authenticated browser /home
    |
    v
Owner-scoped rooms and device assignments in Core
    |
    v
Live Nanoleaf status, quick actions and detailed controls
```

The first bounded Velora device-control slice is implemented:

```text
Text or voice request to Velora
    |
    v
Typed capability proposal
    |
    v
Core-owned room/device resolution, permission and policy validation
    |
    v
Existing integration command path and correlated activity result
```

Explicit German and English imperative requests can now set power or brightness
for every Nanoleaf assigned to one owner-visible room or for one device whose
catalog display name matches exactly and uniquely. For a named device the AI
boundary passes its stable owner-scoped ID, never a provider address. Partial,
duplicate and invented names are not guessed or executed. Core resolves the
target and the existing Nanoleaf service executes the command with one
correlation identifier. The Web chat path returns and persists a deterministic
response based only on Core's result, so browser-backed Voice Mode uses the
same path and never speaks an unconfirmed success.

Core also exposes an authenticated owner-scoped runtime device catalog. It
contains stable connection identity, provider, display name, room and declared
capability identifiers, but no endpoint hosts or credentials. The chat boundary
passes this bounded catalog to the AI service, which only proposes a command
when the requested capability is actually present at runtime. Core still
re-validates the proposal and remains the execution authority.

The runtime catalog now carries typed `online`, `offline`, `degraded` and
`unknown` availability plus an optional observation timestamp. Until a bounded
refresh or event pipeline produces a real observation, existing connections
honestly report `unknown`; Kyrion does not infer that configured means online.

Flyway V10 persists the latest owner-scoped observation per connection. A
CSRF-protected same-origin POST can explicitly refresh at most 20 devices;
catalog reads never trigger provider traffic. Observations remain current for
60 seconds, then the catalog returns `unknown` while retaining the last real
observation timestamp for transparency. Automatic polling and device events
remain planned.

Velora command outcomes now update the same observation store immediately:
successful execution records online, confirmed unavailability records offline
and other adapter failures record degraded. Observation-storage failure remains
secondary and cannot turn a physically successful command into a false failure.

Development hardware for the next integration phase arrived in August 2026.
The Raspberry Pi 5 (8 GB) is now registered as the authenticated `kyrion-node`
gateway and reports bounded health to Core every 5 seconds. Core persists the
latest heartbeat, applies a 45-second offline threshold and exposes owner-scoped
health through the German/English Web gateway view. The Sonoff ZBDongle-E now
runs as an Ember Zigbee coordinator through loopback-only MQTT, and a Philips
Hue colour bulb passed pairing and reversible command validation. The Home
Assistant Connect ZBT-2 and USB voice hardware have not yet been accepted. See
the
[Development Hardware Roadmap](../hardware-roadmap.md).

The gateway view now exposes an owner-triggered, time-bounded Zigbee search with
a visible countdown and paired-device inventory. The Hue test lamp can be
controlled from Web for power, brightness and colour through a persisted,
audited Core command queue polled by the authenticated gateway agent. Live
power, brightness and link quality return through the bounded heartbeat; Web
never receives MQTT access or gateway credentials.

Home now links to a dedicated German/English device-discovery page. It presents
only currently available connection paths, starts Zigbee pairing or local
Nanoleaf discovery after an explicit owner action and presents newly observed
Zigbee candidates with an owner-entered name and explicit Add action. New
supported candidates are no longer imported merely because a heartbeat reports
them. Adding creates or reconciles the stable owner-scoped Core record, after
which `/home` displays it automatically. Existing Home devices can be renamed
and their names and room assignments remain persisted. Supported Philips/Signify
Hue lamps receive the bounded `zigbee.hue_power_on_recover` command
automatically during Add. Web never receives MQTT or provider credentials.
Gateway command polling
is separated from full health collection: commands are checked every 250 ms
while bounded health remains on its five-second cadence. Deployment of the
updated agent service to the physical node was completed on 2026-08-07; the
running systemd command includes `--command-interval 0.25`.

The required lifecycle is now explicit for every future connection method:
discovery alone does not create authority, but once an owner adds or approves a
device, Core creates or reconciles its stable database record and `/home`
displays it automatically. Owner-managed names and room assignments are always
persisted and survive browser, Core and gateway restarts; transient provider
state remains a timestamped observation.

Paired supported Zigbee devices are automatically represented by stable
owner-scoped entries in the shared Core device catalog. They therefore appear
on `/home`, support the existing persistent room assignment flow and expose
power, brightness and colour controls there. Gateway settings retain pairing,
radio status and diagnostics but are no longer a daily device-control surface.

On 2026-08-07 a second Philips Hue LCA011 was paired successfully as
`0x001788010fdcc07d`. Zigbee2MQTT completed its interview, Core automatically
created the stable owner-scoped PostgreSQL entry, and the device entered
`/home` as unassigned. Both Hue lamps store `hue_power_on_behavior=recover` in
the lamp so their last colour and brightness survive a cold power cycle without
Core, Web or the gateway being online. The pairing window was closed again
immediately after verification.

The latest detailed handoff is [Raspberry Pi, Zigbee and Home Integration
Session — 2026-08-06](2026-08-06-raspberry-pi-zigbee-home.md).

## Completed

### Project and architecture

- Monorepo structure for web, mobile, Core, AI and shared contracts.
- Product vision, principles, architecture and roadmap documentation.
- Root `AGENTS.md` with repository-wide quality and architecture rules.
- Marketplace, plugin and enterprise vision.
- Kotlin and Spring Boot Core foundation with a PostgreSQL-backed, append-only
  activity event log.
- Core-owned `GET /v1/activity` contract with data-minimised events and
  correlation identifiers.
- Flyway-managed database schema and an architecture decision record for the
  persistence boundary.
- Identity and server-side session persistence schema prepared in Flyway V2.
- Argon2id password hashing and opaque 256-bit session-token generation.
- Only SHA-256 session-token hashes are designed to be stored; raw session
  tokens are returned once for the future protected cookie.
- Tested session lifecycle domain logic for creation, seven-day expiry,
  last-seen updates, authentication and revocation.
- One-time local-owner setup, login, current-user and logout HTTP contracts.
- Same-origin `HttpOnly`, `SameSite=Strict` session cookie and double-submit
  CSRF protection at the Next.js boundary.
- Authoritative protection for workspace pages, private Next.js APIs and Core
  activity/conversation resources.
- Owner-scoped PostgreSQL conversations and ordered messages through Flyway V3.
- Core-owned chat turns and token-bounded context assembly; the browser no
  longer supplies authoritative conversation history.
- Flyway V4 persistence for deterministic context summaries with source ranges
  and algorithm versions.
- Flyway V5 turn lifecycle with explicit started, completed, stopped and failed
  outcomes, including server-observed partial response persistence.
- Flyway V6 owner-controlled personal memory with opt-in, explicit proposals,
  confirmation, correction and deletion.
- Flyway V7 conflict links and explicit replace/keep-both/forget resolution;
  superseded memories remain inspectable but are excluded from retrieval.
- Deterministic Core-owned retrieval supplies at most three relevant confirmed
  memories, applies stricter matching to sensitive items and visibly discloses
  every selected item in the chat.
- Complete conversation-history interaction with active highlighting, inline
  rename, confirmed deletion, explicit empty/error states and visible save
  failures.
- Readable automatic titles based on the first sentence, always beginning with
  a capital letter.
- AI actions remain proposals and the first Nanoleaf power/brightness device
  actions pass through Core-owned target resolution, validation and execution.
- Official Nanoleaf integration connections are owner-scoped, use physical
  local-controller pairing and keep API tokens encrypted in Core persistence.
- Nanoleaf power, brightness, colour, colour-temperature and scene commands run
  through Core validation and emit integration activity events.
- Flyway V8 persists encrypted owner-specific integration connections. The
  AES-256-GCM installation key remains separate from PostgreSQL.
- Flyway V9 persists owner-specific rooms and device assignments. Deleting a
  room leaves its devices connected and unassigned.
- Flyway V11 persists short-lived one-time gateway enrollments, hashed gateway
  credentials and the latest typed node-health heartbeat.
- The Debian ARM64 gateway agent is installed as a hardened unprivileged
  systemd service on `kyrion-node`; it has no sudo, Docker socket or general
  remote-command authority.
- A source-restricted Windows firewall rule allows Core traffic on TCP 8080
  only from the Pi's reserved Wi-Fi and Ethernet addresses.

### Web application

- Next.js 16, React 19, TypeScript and Tailwind CSS foundation.
- Persistent shared application shell using a workspace route group.
- Responsive sidebar and accessible mobile shadcn Sheet.
- Chat, Home, Automations, Knowledge and Settings routes.
- A Plugins catalog and an interactive Nanoleaf integration detail route.
- A working Home dashboard with room management, persistent device assignment,
  explicit bounded status refresh, quick actions and per-device control dialogs.
- Passive provider-neutral availability display with a visible bounded refresh,
  last-observed timestamps and distinct unknown/degraded/offline states.
- Home quick-power actions use the same provider-neutral `power.set` Core path
  as Velora, selecting exactly one owner-scoped stable device identifier and
  updating the shared observation store.
- Nanoleaf discovery, editable names, colour controls and stored scenes with
  controller-derived palette previews.
- German and English UI resources.
- Persistent light/dark theme selection.
- Per-device typography selection with standard, comfortable and large scales
  for body text, headings and display titles.
- White/gold light theme and cyan/royal-blue dark theme.
- Provider-neutral typed chat contracts.
- Streaming chat UI with cancellation and translated errors.
- Markdown rendering, intelligent autoscroll and refined stream states.
- One validated conversation identifier per mounted chat session.
- Live AI-service readiness and configured-model status.
- Dedicated local-model page with validated Ollama metadata and per-device
  selection.
- Initial conversational Voice Mode opened from the Velora orb, using browser
  speech recognition and system speech synthesis as transparent prototype
  providers.
- Sentence-based streaming speech: completed sentences begin playing while the
  model continues generating later sentences.
- Voice turns are isolated by assistant message ID so prior conversation text
  and cancelled browser utterances cannot enter a new response queue.
- Centred Voice Mode layout with a wider transcript, automatic spoken-word
  tracking and a subtle animated focus outline.
- Dedicated voice settings with per-language browser voice selection, previews,
  local/online labels and a persisted speaking rate.
- Primary Activity navigation backed by persisted Core events, including clear
  loading, unavailable and empty states.
- Runtime validation of Core responses in the Next.js server-side proxy.
- Next.js server-side `/api/chat` proxy; Ollama is never called directly by the
  browser.

### AI service

- Python 3.12 project using FastAPI, Pydantic, HTTPX and Uvicorn.
- Provider-neutral `LanguageModelProvider` protocol.
- Ollama provider using `/api/chat` with NDJSON streaming.
- Reasoning-capable models use visible answer streaming without an invisible
  thinking pass; models remain warm for ten minutes and use a 4096-token
  runtime context for normal chat.
- Stable Kyrion chat events and error codes.
- Modular Kyrion-owned Velora system prompt with local-first and safety rules.
- Request validation, health endpoint and tests.
- Local virtual environment at `services/ai/.venv` (ignored by Git).

### Local runtime

- PostgreSQL 17 development container bound only to localhost.
- PostgreSQL files stored through a bind mount at
  `E:\Kyrion\Data\postgres`, not an anonymous Docker volume on C:.

- Ollama 0.32.5 installed at `E:\Ollama\App`.
- Physical model storage at `E:\Ollama\Models`.
- `C:\Users\Flo\.ollama\models` is an NTFS junction to the E: model directory
  because this Ollama Windows build continued to resolve its default path.
- Installed and verified models:
  - `gemma3:4b` (default Kyrion model);
  - `qwen3:8b` (alternative model).
- Both models load fully on the NVIDIA RTX 2070 8 GB using 100% GPU execution
  at a 4096-token context during the smoke test.

## Verification completed

- `pnpm lint`: passed.
- `pnpm build`: passed, including the dynamic chat and model benchmark routes.
- Python Ruff checks: passed.
- Python tests: 33 passed at the latest full AI-service verification.
- Kotlin Core tests and boot JAR build: passed.
- Flyway migrations V1 through V10, Core health and persisted startup events: passed
  against PostgreSQL.
- Password hashing, session-token hashing and session lifecycle tests: passed.
- Isolated PostgreSQL 17 integration tests for one-time setup, HTTP auth
  contracts, password rotation and conversation owner isolation: passed.
- Web authentication policy tests for `HttpOnly`, `SameSite`, `Secure` and CSRF
  token matching: passed.
- Web `/api/activity` end-to-end response: passed.
- Warm `qwen3:8b` smoke test produced its first visible token in about 0.52
  seconds and completed a short response in about 0.63 seconds on the current
  machine; this is an observation, not a performance guarantee.
- Ollama API health: passed.
- `gemma3:4b` inference: passed.
- `qwen3:8b` inference: passed.

## Current limitations

- New user turns are persisted before model invocation and completed assistant
  responses are persisted before the browser receives the completion event.
- A visibly stopped partial assistant response is persisted from the trusted
  Next.js stream boundary.
- Deterministic context compaction is implemented; automatic retention is not.
- Personal memory supports explicit owner-controlled retention and transparent
  retrieval; semantic retrieval and retention expiry are not implemented.
- The current development installation has one configured local owner; public
  registration remains unavailable by design.
- Core currently implements activity, local authentication, conversations,
  personal memory, rooms and the first broad Nanoleaf integration slice;
  provider-neutral capability contracts and broader plugin lifecycle remain
  planned.
- Activity actor ownership, retention and tamper-evidence are not implemented.
- Available models remain deployment-controlled through `KYRION_ALLOWED_MODELS`;
  each browser can select one locally for its chat requests.
- Model benchmark results currently live only in page state and are discarded
  when the model page is left or reloaded.
- Voice Mode currently depends on browser speech APIs. Speech recognition may
  use an external browser service and is not yet Kyrion's planned local voice
  pipeline.
- Voice interruption while Velora is actively speaking is not yet a complete
  hands-free barge-in flow because continuous recognition could hear the
  assistant's own browser speech.
- Automations and Knowledge are intentional placeholders. Home is implemented.
- Controller addresses are not yet reconciled automatically after DHCP changes.
- Dashboard catalog status loads without provider traffic. A visible bounded
  manual refresh and last-observed timestamps are implemented; automatic
  polling and device events remain planned.
- Removing a connection does not yet revoke its token on the physical controller.
- Velora device commands currently support only explicit imperative German and
  English Nanoleaf power/brightness phrases with exact room names or exact,
  unique catalog device names. Colours, scenes, partial-name matching,
  clarification dialogue and pronoun/context resolution remain planned. The
  runtime catalog is still an internal first-party contract and needs
  stabilisation before adapters or plugins may depend on it.
- An individual qualifier such as "left" is not silently discarded. It is only
  executable when it is the complete unique display name of a catalog device;
  otherwise no device command is proposed.
- Gateway heartbeat continuity across a full Pi reboot and temporary network
  loss is not yet recorded. Wi-Fi is configured but currently disconnected;
  its failed boot association remains a separate diagnostic follow-up.
- The Sonoff Zigbee adapter and one Philips Hue colour lamp are accepted end to
  end. The ZBT-2 Thread/Matter adapter and USB voice hardware remain
  unvalidated.
- Zigbee currently auto-imports supported paired devices. A discovery inbox
  with explicit approval, naming, rejection, removal and re-pairing remains.
- Zigbee Web commands currently wait synchronously for the outbound gateway
  agent. An asynchronous command-status flow is required before scaling.

## Recommended next step

The market and user-needs analysis sharpened Kyrion's position: it should be an
understandable, secure and reliably operated orchestration layer above existing
systems, not a Home Assistant clone or an unrestricted assistant. Home
Assistant will provide optional integration breadth through a bounded adapter;
Kyrion continues to own identity, capabilities, household permissions, policy,
diagnosis, audit and recovery. Native integrations remain selective, with
Nanoleaf as the current reference adapter. The full rationale is recorded in
[Product Strategy](../product-strategy.md).

Integration onboarding will not force a read-only first phase. The owner will
select Observe, Control or Manage access, implemented as granular Core-enforced
permissions rather than unrestricted provider access. Material onboarding,
permission elevation, pairing and migration will be protected by a pre-change
restore point spanning every supported component. Backup coverage and actual
restore verification remain separate visible facts. This accepted direction is
recorded in
[ADR 0006](../adr/0006-integration-access-profiles-and-pre-change-restore-points.md).

The current planning checkpoint separates the remaining work into three
dependency lanes.

### Implementable now

1. stabilise provider-neutral device identity, state, capability, command and
   result contracts above the working Nanoleaf slice;
2. implement the Core-owned Device Manager and household/member role foundation;
3. define action policies, confirmations, correlated audit and integration
   health explanations;
4. add an optional Home Assistant adapter with owner-selected Observe, Control
   or Manage access that translates into Kyrion-owned contracts;
5. move natural-language target resolution into the Device Manager
   that supports stable IDs, exact rooms, display names and capabilities;
6. add an explicit clarification dialogue for genuinely ambiguous targets;
7. add the remaining boundary tests for ambiguity, unavailable capability,
   adapter failure, malformed AI output and cross-owner access;
8. prepare provider-neutral Device Manager, Integration Manager, discovery
   inbox and gateway/voice-satellite health surfaces in German and English.

### Awaiting owner physical verification

- fresh authentication and Home quick power control were physically verified
  successfully on 2026-08-05;
- repeat the German text command after the room-alias latency fix, then exercise
  brightness, English and browser-backed Voice Mode commands;
- verify explicit status refresh against the physical controllers;
- verify accurate feedback when a controller is unavailable. This validation
  is intentionally deferred until the owner resumes physical testing.

The first German text test exposed that the spoken/written room variant
`Gamingraum` did not match the stored `Gamingroom`. Core rejected the raw room
quickly, but the subsequent correction fell through to the general model and
produced a slow non-executing wait message. The bounded proposal path now maps
`room`/`raum` variants only when exactly one capability-compatible catalog room
matches and can apply an explicit room correction to the preceding command.
This is covered by AI regression tests and a live proposal check; physical
execution remains to be repeated by the owner.

### Physical gateway and protocol validation

- the dedicated Sonoff Zigbee adapter and first Hue device are validated;
  attach and validate the Thread adapter and USB voice hardware through stable
  device identities;
- prove heartbeat recovery across a full Pi restart and temporary network loss;
- prove Zigbee, Matter-over-Thread, Wi-Fi, Bluetooth and voice as separate
  end-to-end slices rather than treating discovery or pairing as completion.

Cross-cutting follow-up remains local STT/TTS and wake-word interruption,
bounded background device events, DHCP recovery, login throttling, session and
retention controls, physical token revocation and implementation of the
accepted restore-point and verified-restore design.
This priority must not weaken Core authority, local-first operation or
auditability.

Do not expose the prepared session repository directly and do not store tokens
in browser local storage. Continue with one verified vertical slice at a time.

## How to resume

In a new agent chat, use this prompt:

> Read `AGENTS.md`, `README.md`, all project-owned files in `docs/`, especially
> `docs/status/README.md`, `docs/status/TODO.md` and all ADRs. Inspect the
> current implementation and uncommitted changes. Read the latest dated session
> handoff. Verify Core and the three Pi services, then confirm the paired Hue is
> visible and controllable on `/home`. Continue with explicit Zigbee
> discovery/approval/name/remove lifecycle, asynchronous command status and
> focused gateway-command tests. Preserve Core as authority and the
> outbound-only agent boundary. Do not begin Thread/Matter until the Zigbee
> lifecycle and recovery work is understood. Never store credentials or
> session tokens in browser local storage.

For runtime commands, see [Local Development Startup](../development-startup.md).

The concrete next-session tasks are tracked in [TODO.md](TODO.md).

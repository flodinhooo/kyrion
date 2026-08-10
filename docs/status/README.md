# Kyrion Development Status

Last updated: 2026-08-10

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
Assistant Connect ZBT-2 has not yet been accepted. The Delock microphone and
Pebble V3 Bluetooth speakers passed capture, playback and reboot-reconnect
acceptance on 2026-08-08. See
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

The bounded Zigbee heartbeat now includes live power, percentage brightness,
hue, saturation and colour-temperature values. The Core device catalog joins
that state to approved devices by stable IEEE identity and exposes a separate
immutable hardware description alongside the owner-editable display name.
`/home` therefore shows names such as “Hue entrance” without hiding the actual
Philips model, plus current power, brightness and a colour preview. MQTT topics
and raw provider access remain hidden from Web.

Home also performs a bounded automatic Nanoleaf state refresh for at most 20
owner connections every ten seconds. The controller-reported name (for example
the Light Panels family plus its short identifier), power, brightness and colour
are displayed without requiring the manual global refresh button. Device power
is presented consistently as a separate green On or red Off state; provider
availability remains a distinct diagnostic signal.

Paired supported Zigbee devices are automatically represented by stable
owner-scoped entries in the shared Core device catalog. They therefore appear
on `/home`, support the existing persistent room assignment flow and expose
power, brightness and colour controls there. Gateway settings retain pairing,
radio status and diagnostics but are no longer a daily device-control surface.

On 2026-08-07 a second Philips Hue LCA011 was paired successfully as
`0x001788010fdcc07d`, explicitly named and added by the owner, and assigned to
the persisted `Gang` room. A direct database check confirmed that both Hue
records retain their stable IEEE identity and room assignment. Both
Hue lamps store `hue_power_on_behavior=recover` in
the lamp so their last colour and brightness survive a cold power cycle without
Core, Web or the gateway being online. The pairing window was closed again
immediately after verification.

The latest detailed handoff is [Qwen Streaming Spike Closeout —
2026-08-10](2026-08-10-qwen-streaming-closeout.md). The wake-word handoff
remains [Voice Satellite and Wake-Word Session —
2026-08-09](2026-08-09-voice-satellite-wake-word.md).

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
- Route-specific browser titles replace the former shared product tagline.
- Approved theme-aware Kyrion SVG assets are used consistently: the full
  lockup in the sidebar, K-Core on the login surface and the transparent
  small-size mark as favicon. `branding/brand-guide.md` is authoritative.
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
- The Sonoff Zigbee adapter and two Philips Hue colour lamps are accepted end to
  end. The Delock USB microphone and Pebble V3 audio output are accepted. The
  ZBT-2 Thread/Matter adapter remains unvalidated.
- Zigbee discovery requires explicit approval and naming. Owner-confirmed
  removal publishes the bounded Zigbee2MQTT remove request through the gateway,
  deletes the Core record only after success and permits subsequent re-pairing.
- Interactive Zigbee controls enqueue asynchronously and expose pending,
  succeeded and failed gateway state. Broader retry, timeout and idempotency
  hardening remains before scaling.
- The 2026-08-08 Pi audio acceptance found the Delock microphone through its
  stable ALSA identity and the Pebble V3 as the connected BlueZ/PipeWire default
  sink. Temporary capture and direct/browser playback passed. The authenticated
  heartbeat exposes only bounded endpoint metadata in the bilingual gateway
  view. A non-privileged Voice Satellite user service now performs continuous
  local openWakeWord ONNX inference for `Hey Velora`; the first live Pi utterance
  was detected at score `0.601`. A second test candidate trained with 40
  reviewed real-room positives and four hard `Velora` negatives is deployed
  with the baseline retained for rollback. Synthetic validation changed from
  `0.417` to `0.389` recall and from `1.062` to `0.354` false positives/hour;
  an independent 11-clip real-room holdout improved from 4/11 to 5/11 detected
  at threshold `0.5`, while the held-out `Velora` negative remained rejected.
  The small holdout and missed positives mean the model remains a test
  candidate and requires broader physical evaluation before production.
  Stronger real-feature weighting was rejected after two controlled follow-up
  candidates: both detected all 11 held-out complete phrases, but also accepted
  the sole held-out `Velora`-only example. A `0.97` threshold separated this
  single room holdout but reduced synthetic positive recall to 4/3000, proving
  session over-specialisation rather than general improvement. The safer second
  candidate remains deployed. More independent partial-phrase negatives and
  cross-microphone positives are required before another candidate is accepted.
  The bounded post-wake PCM uplink prototype and its physical Pi acceptance are
  complete. Faster-Whisper rolling-window streaming was rejected for final
  latency. Nemotron 3.5 CPU Q8 then achieved stable sub-second finals and no
  noise hallucinations, but tied rather than clearly beat the preserved
  `small/int8` sentence-quality gate and regressed `desk lamp`; it is therefore
  not approved for integration. Streaming TTS and interruption remain planned.

## Recommended next step

The local voice architecture gate passes for an isolated Qwen 1.7B
prototype. The owner selected the non-crossfaded 10-frame first decode followed
by 20-frame strides because it sounds almost identical to the full decode. Its
mean TTS TTFA is 2.309 seconds. Phase 3.1 now provides a bounded authenticated
HTTP/NDJSON PCM16 uplink from the already-woken satellite to Core with typed
session, turn, audio-format, capture-time and sequence metadata. Core processes
the request incrementally, retains no audio and returns frame, byte and latency
measurements. Automated and physical transport acceptance pass. The subsequent
Faster-Whisper rolling and Nemotron 3.5 incremental STT spikes are both no-go
for production: the former misses the latency gate and the latter does not
clearly win the quality gate. Keep the current final `small/int8` fallback and
do not add STT integration, TTS downlink, playback buffering, dialogue
replacement or barge-in on the strength of either spike.

Phase 3.2 is now formally closed under weighted future STT acceptance criteria.
Faster-Whisper `small/int8` remains the productive bounded-final baseline and
Nemotron is frozen as a documented no-go. Phase 3.3 has begun with an isolated
authenticated synthetic PCM downlink contract and validating Satellite client.
It remains disconnected from providers, the Dialogue Controller and playback;
physical Pi transport acceptance was the next gate and has now passed at the
selected 160 ms framing. Four 20-second runs were complete and real-time paced,
with stable Core memory, authentication rejection, cancellation and reconnect.
The next isolated slice is a bounded Satellite jitter buffer using synthetic
frames; it remains separate from TTS providers and dialogue routing.

The bounded jitter buffer and raw PipeWire sink subsequently passed physical
Pi acceptance. The initial just-in-time PipeWire feed produced audible gaps;
the same buffered PCM sounded perfect, isolating the issue to downstream
priming. After forwarding the complete 320 ms prebuffer immediately, the owner
confirmed two clean streaming-tone runs. Phase 3.5 is accepted without adding a
TTS provider or production dialogue integration.

Phase 3.6 now defines the provider-neutral AI-side streaming-TTS contract with
typed capabilities, phrase scope, PCM bounds, sequence validation and bounded
cancellation. Phase 3.7 adds an isolated Qwen mapping tested against a mock
runtime. Phase 3.8 proves the same mapping against a real isolated runtime:
typed streaming and 208.3 ms cancellation pass, and the owner accepted the
short DE/EN samples. Qwen nevertheless remains a no-go because first audio
takes 2.4–2.7 seconds, updates pause for 4.3–4.6 seconds and a longer sample
has an audible boundary jerk. Core and provider selection remain unchanged.

Phase 3.9 adds the next provider-neutral stage in isolation: incremental LLM
text is segmented into bounded TTS phrases with domain-term preservation,
abbreviation handling and cancellation. It is covered by the 69 passing AI
tests and remains disconnected from the production chat route. The next safe
slice is a synthetic composition test, not provider or Core integration.

Phase 3.10 completes that synthetic composition: ordered phrases become
validated PCM events, totals remain turn-scoped and one shared cancellation
prevents later phrases from starting. The AI suite now has 71 passing tests.
Further production wiring is intentionally gated on an accepted streaming-TTS
runtime; Qwen does not satisfy that gate.

Phase 3.11 now defines the shared streaming-TTS gate. A candidate must provide
true incremental PCM, P95 first audio within two seconds, long-form RTF below
0.90 and uninterrupted playback after the accepted 320 ms prebuffer. It must
also pass bounded cancellation, stability, concurrent GPU headroom, licensing
and owner listening weighted toward Velora identity, domain pronunciation and
boundary continuity. TTFA alone can no longer qualify a runtime.

Phase 3.12 selects `Fun-CosyVoice3-0.5B-2512` as the only next isolated spike
candidate based on official DE/EN zero-shot cloning, bi-streaming, 0.5B size
and Apache-2.0 project evidence. This is not an integration approval. Model
load, artifact licensing, RTX 2070 compatibility and one Velora DE/EN proof
must pass in the training WSL environment before the full acceptance matrix.

The CosyVoice proof subsequently failed that cheap gate. With cached Velora
conditioning and a warm model, first PCM took 4.2–5.4 seconds; five of six
DE/EN runs emitted the complete phrase as their only chunk, and observed RTF
was roughly 0.94–1.52. The full stability/listening matrix is therefore not
justified. CosyVoice joins Qwen as a documented no-go, while Chatterbox remains
the operational batch fallback and no Core integration is added.

Phase 3.13 verifies that Chatterbox itself remains a healthy batch fallback: a
silent local request returned a valid 3.28-second mono 24 kHz PCM16 WAV in
3.624 seconds and unknown voices fail explicitly. The AI configuration still
labels its local HTTP client as Qwen even though that transport shape is also
used by Chatterbox. This naming/configuration debt is documented for the next
bounded slice; no endpoint was silently switched.

Phase 3.14 resolves that debt without adding fallback selection: `http_batch`
and `KYRION_HTTP_TTS_URL` now name the existing local batch contract, while an
explicit legacy `qwen` selection retains its old endpoint. The real client to
Chatterbox returned valid mono 24 kHz PCM16, and the AI suite has 72 passing
tests. Streaming and Core remain unchanged.

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
  the USB voice hardware and local wake-word test path are validated; attach
  and validate the Thread adapter through a stable device identity;
- prove heartbeat recovery across a full Pi restart and temporary network loss;
- prove Zigbee, Matter-over-Thread, Wi-Fi, Bluetooth and voice as separate
  end-to-end slices rather than treating discovery or pairing as completion.

Cross-cutting follow-up remains wake-word model quality, local STT/TTS and interruption,
bounded background device events, DHCP recovery, login throttling, session and
retention controls, physical token revocation and implementation of the
accepted restore-point and verified-restore design.
This priority must not weaken Core authority, local-first operation or
auditability.

Do not expose the prepared session repository directly and do not store tokens
in browser local storage. Continue with one verified vertical slice at a time.

## How to resume

In a new agent chat, use this prompt:

> Read `AGENTS.md`, `README.md`, `docs/status/README.md`,
> `docs/status/TODO.md`, the Phase 3.1 report, both 2026-08-10 STT spike reports,
> ADR 0009 and the Qwen streaming closeout. Inspect uncommitted changes. Phase
> 3.1 physical PCM uplink acceptance passed. Faster-Whisper rolling streaming
> and Nemotron 3.5 integration were both rejected; retain bounded final
> `small/int8` and Chatterbox as fallbacks. Do not change Core or the Voice
> Pipeline unless a new stateful local STT candidate clearly wins the preserved
> private quality and latency benchmark.

For runtime commands, see [Local Development Startup](../development-startup.md).

The concrete next-session tasks are tracked in [TODO.md](TODO.md).

# Kyrion Development TODO

Last updated: 2026-08-10

This file contains the immediate continuation point for the next development
session. The current implementation status is documented in [README.md](README.md).

## Next session: Local voice Phase 3

- [x] Preserve the immutable provider-neutral `velora-f` voice profile and its
  original Qwen reference, transcript, checksum and provenance.
- [x] Benchmark Qwen 1.7B internal codec-frame streaming on the RTX 2070 with
  cached F conditioning, warm FP16 runtime, cancellation and bounded memory.
- [x] Complete the owner's listening gate. Accept `start 10, then 20` without
  crossfade as the spike candidate: it is nearly full-decode quality to the
  owner, averages 2.309 seconds to first PCM and avoids the crossfade variant's
  larger measured worst boundary jump.
- [x] Phase 3.1: define and implement only a typed authenticated continuous
  PCM16 uplink prototype from the already-woken Voice Satellite to a bounded
  Core ingress. Include `sessionId`, `turnId`, sample rate, channel count and a
  monotonically increasing frame sequence; record transport timing.
- [x] Complete physical Pi-to-Core acceptance for ordering, bounded buffering,
  authentication failure, disconnect, cancellation, reconnect and measured
  latency. Three 20-second Pi runs delivered 250 frames each with stable Core
  memory; the reference run measured 2-12 ms after per-session clock
  calibration. Authentication, cancellation, disconnect and reconnect passed.
- [x] Phase 3.2 spike: measure CPU-int8 Faster-Whisper rolling STT separately.
  Real Delock German/English, silence/noise and correction tests reject the
  design for production: `small` full-window recomputation delays authoritative
  finals to roughly 2.4-2.9 seconds when a partial is in flight, while `base`
  is fast enough but loses too much German command meaning. Keep final-utterance
  `small/int8` as fallback and do not wire either rolling design to Core.
- [x] Evaluate Nemotron 3.5 ASR as a genuinely stateful incremental local STT
  candidate against the preserved private Delock set. Its CPU Q8 runtime has
  stable partials, zero hallucinations across six noise clips and under 0.49
  seconds mean EOS-to-final latency at 160 ms chunks, but only ties
  `small/int8` at 16/20 usable sentence meanings and regresses `desk lamp`. Do
  not integrate it or replace the existing final-transcript fallback.
- [x] Close Phase 3.2 with Nemotron retained as a documented no-go and
  Faster-Whisper `small/int8` retained as the productive bounded-final baseline.
- [x] Define shared future STT acceptance criteria with fivefold weighting for
  `Velora`, room and device identity, hard safety/latency/resource gates and a
  clear-win threshold beyond aggregate WER.
- [ ] Leave production streaming STT unplanned until another stateful local
  candidate clearly beats the preserved `small/int8` quality gate, including
  `Velora`, `Gamingraum`, `desk lamp` and interrupted self-correction.
- [x] Keep Chatterbox operational as the batch fallback and do not make the
  Qwen spike a production provider until a later provider-adapter phase.
  The Phase 3.13 smoke check returned a valid 3.28-second mono 24 kHz PCM16 WAV
  in 3.624 seconds and rejected an unknown voice. No audio was played.
- [x] Phase 3.3 software prototype: add only a provider-neutral authenticated
  bounded PCM downlink with synthetic PCM and strict session/turn, format,
  sequence, size, total and local-cancellation validation. Keep it disconnected
  from the production Satellite runtime and every speech provider.
- [x] Complete Phase 3.3 physical Pi acceptance. Four 20-second 160 ms runs
  delivered 125 frames and 960,000 bytes each in 19.85–19.88 seconds with
  stable Core memory; cancellation, authentication rejection and reconnect
  passed. The unstable 80 ms framing is rejected.
- [x] Phase 3.4: add and verify only a bounded Satellite PCM jitter buffer with
  synthetic frames, explicit prebuffer, backpressure, underflow metrics and
  cancellation clearing. The silent Pi test consumed 125/125 frames with a
  two-frame peak, no underflow/drop and correct queued-frame cancellation.
- [x] Phase 3.5: add a bounded raw-PCM PipeWire sink and physically verify the
  Creative Pebble output. The corrected two-frame downstream priming sounded
  clean in two owner-confirmed streaming runs; completion and 59 ms
  post-signal cancellation pass. Keep it disconnected from TTS and dialogue.
- [x] Phase 3.6: define the smallest provider-neutral streaming-TTS contract
  behind the existing AI boundary, including format/capability declaration,
  cancellation and phrase granularity. Do not wire Qwen into Core until the
  contract and an isolated adapter test pass. The contract now validates typed
  start/audio/terminal events, provider capabilities, bounds and cancellation.
- [x] Phase 3.7: implement and test an isolated Qwen mapping against a mocked
  capability-reporting streaming runtime. Keep it unavailable for selection
  because the current real Qwen runtime does not implement that interface.
- [x] Phase 3.8: add the capability and bounded NDJSON streaming interface to
  the isolated Qwen runtime and rerun the gate through the real adapter.
  Capability, terminal and 208.3 ms cancellation behaviour pass, and the owner
  accepted the short DE/EN quality samples. Integration is rejected because
  first audio takes 2.4–2.7 seconds, update gaps reach 4.3–4.6 seconds and one
  longer sample has an audible codec-boundary jerk. Keep Qwen isolated.
- [ ] Do not schedule Qwen/Core integration. The next local streaming-TTS
  candidate must sustain generation faster than playback, provide continuous
  bounded chunks and preserve the accepted voice quality and cancellation.
- [x] Phase 3.9: implement and test only the provider-neutral LLM-text to TTS
  phrase-boundary policy. It emits bounded DE/EN sentences incrementally,
  preserves domain names, avoids common abbreviation splits and discards
  buffered text on cancellation. Keep it disconnected from production chat.
- [x] Phase 3.10: compose a mock LLM text stream, the phrase boundary and a
  synthetic streaming-TTS provider. Phrase/audio ordering, per-phrase sequence,
  totals and shared cancellation pass without provider or Core integration.
- [ ] Resume Voice Pipeline integration only after a local streaming-TTS
  provider passes continuous faster-than-playback generation, voice quality,
  cancellation, stability, memory and licence gates. Until then retain the
  working batch dialogue and avoid speculative Core wiring.
- [x] Phase 3.11: define shared streaming-TTS acceptance criteria. Treat
  continuous post-prebuffer playback, long-form RTF below 0.90, bounded chunk
  deadlines and critical Velora/domain/boundary listening scores as hard gates,
  rather than accepting TTFA alone.
- [x] Select at most one new local streaming-TTS candidate for an isolated
  Phase 3.12 spike based on official streaming, cloning, licence and RTX 2070
  feasibility evidence. `Fun-CosyVoice3-0.5B-2512` is selected because its
  official project supports DE/EN zero-shot cloning and bi-streaming under an
  Apache-2.0 code licence. Do not integrate it or download other candidates.
- [x] Install CosyVoice 3 only in the isolated training WSL environment and
  prove model load plus one DE/EN `velora-f` clone before running the full
  Phase 3.11 acceptance matrix. The cached warm proof fails early: first PCM
  takes 4.2–5.4 seconds, five of six outputs arrive as a single complete chunk,
  and warm RTF is roughly 0.94–1.52. Freeze CosyVoice as a no-go.
- [ ] Leave streaming-TTS provider selection open. Qwen and CosyVoice are
  documented no-go candidates on the RTX 2070; Chatterbox remains the working
  batch fallback and the synthetic provider-neutral contracts remain ready.
- [x] Replace the Qwen-specific name of the existing AI-side local batch HTTP
  TTS client with an explicit provider-neutral name. Preserve Piper and typed
  failure behaviour; do not add silent fallback, streaming or Core changes.
  `http_batch` now targets the explicit `KYRION_HTTP_TTS_URL`; the real
  Chatterbox acceptance returned valid mono 24 kHz PCM16 and all 72 tests pass.

Do not begin the Pi audio downlink, production Dialogue Controller changes,
WebSocket/NDJSON TTS streaming, playback buffer or barge-in in Phase 3.1.

## Completed: Local authentication and ownership

- [x] Add an identity and session database schema without creating a default
  user or exposing public registration.
- [x] Hash passwords with Argon2id using unique salts.
- [x] Generate opaque 256-bit session tokens and persist only SHA-256 hashes.
- [x] Implement and test session creation, expiry, last-seen updates and
  revocation in Core.
- [x] Add a one-time local-owner setup endpoint and setup screen.
- [x] Add Core login, current-user and logout endpoints.
- [x] Set the session through a same-origin `HttpOnly` and `SameSite` cookie;
  use `Secure` whenever Kyrion is served over HTTPS.
- [x] Add CSRF protection to authenticated state-changing requests.
- [x] Protect private Core and Next.js routes through authoritative session checks.
- [x] Add automated integration coverage that proves owner isolation with two
  users before multi-user setup is introduced.
- [x] Record authentication success, failure and logout as data-minimised
  security activity events without logging credentials or raw tokens.
- [x] Add automated tests for cookie flags, CSRF validation, invalid
  credentials, expiry, revocation, session rotation and PostgreSQL owner
  isolation.
- [x] Add authenticated password change with current-password verification,
  revocation of all existing sessions and a fresh session cookie.

## Completed chat and voice refinement

- [x] Render assistant responses as Markdown instead of displaying Markdown
  syntax such as `**bold**` as plain text.
- [x] Add polished styling for headings, paragraphs, lists, links, inline code
  and fenced code blocks in both themes.
- [x] Improve spacing and readable line lengths for longer responses.
- [x] Add persistent standard, comfortable and large typography options that
  scale body text, headings and page titles without enlarging layout chrome.
- [x] Keep the conversation scrolled to the newest content while a response is
  streaming, without overriding intentional user scrolling.
- [x] Add a Kyrion/Velora system prompt so the assistant identifies itself as
  Velora and describes its role accurately instead of repeating the base
  model's identity.
- [x] Define sensible defaults for response language, tone and length.
- [x] Refine the loading, stop-generation and error states.
- [x] Manually exercise the primary chat, history and authentication flows in
  both light and dark mode.
- [ ] Complete a systematic German and English visual pass for every settings
  and error state.

## Verification

- [x] Run `pnpm lint`.
- [x] Run `pnpm build`.
- [x] Start the full local stack using
  [Local Development Startup](../development-startup.md).
- [x] Send short, long and list-based prompts through
  `http://localhost:3000`.
- [ ] Add a dedicated code-block prompt to the next visual regression pass.
- [x] Confirm that streaming and continued persisted conversations work after
  adding Markdown rendering.

## After the chat refinement

- [x] Add an AI-service readiness state to the web status indicator.
- [x] Add a controlled per-device model selector backed by the deployment
  allowlist.
- [x] Add a dedicated model page with metadata from the local model runtime.
- [x] Add a controlled per-device benchmark with a transparent model
  recommendation.
- [x] Introduce conversation identifiers.
- [x] Add an initial browser-backed Voice Mode opened from the Velora orb.
- [x] Add per-language browser voice selection, previews and speaking-rate
  controls.
- [x] Stream visible answer tokens immediately for reasoning-capable models
  without waiting for an invisible Qwen thinking pass.
- [x] Begin speaking completed sentences while later answer text is still being
  generated.
- [x] Isolate voice turns so old messages and cancelled utterance callbacks do
  not enter the next response queue.
- [x] Add a centred, wider Voice Mode transcript with subtle spoken-word focus.
- [ ] Replace prototype browser speech recognition and system TTS with
  explicitly selected local providers.
- [x] Train and deploy the first local `Hey Velora` ONNX wake-word candidate as
  a non-privileged Pi user service; prove one live Delock microphone detection.
- [x] Train and deploy a second wake-word test candidate with reviewed room
  examples, a deterministic holdout and a rollback copy; record its mixed
  synthetic and real-room comparison honestly.
- [ ] Broaden physical wake-word evaluation and improve missed-phrase recall,
  then add interruption and voice-device settings above the accepted Pi audio
  endpoints.
- [ ] Record a dedicated independent `Velora`-only negative set and positive
  holdouts across the Pi microphone and at least one phone microphone before
  accepting another strongly personalised wake-word candidate.
- [ ] Keep V2 deployed until V5 passes independent complete-phrase,
  partial-phrase and cross-microphone holdouts; never deploy the archived V3 or
  V4 overfit experiments merely because they reached 11/11 same-session recall.
- [ ] After V5 acceptance, build the bounded first-dialog slice in this order:
  acknowledgement tone, VAD-bounded post-wake capture, authenticated Core
  delivery, local STT, existing assistant routing, local TTS and Pebble output.
- [x] Add `/activity` to the primary navigation with an honest Core-bound empty
  state.
- [x] Define the Core-owned activity event contract and append-only log.
- [x] Connect `/activity` to persisted Core events without exposing sensitive
  payloads.
- [x] Define the Core/database boundary for conversation persistence.
- [x] Add a local PostgreSQL development database after the first Core contracts
  are stable.
- [ ] Add authenticated actor ownership, retention policy and tamper-evidence to
  the activity log before treating it as a compliance audit trail.
- [x] Add active conversation highlighting, editable titles, confirmed
  deletion, history states and visible persistence errors.
- [x] Add owner-scoped PostgreSQL conversation and message persistence after the
  authentication slice is complete.

## Next session: Authoritative context and compaction

- [x] Document the typed contract for Core-owned conversation context supplied
  to the AI service.
- [x] Load stored messages by authenticated owner and conversation ID instead of
  treating a browser-supplied full transcript as authoritative.
- [x] Define a transparent context token budget for the selected models under
  the current shared 4,096-token runtime configuration.
- [x] Preserve the latest turns verbatim while compacting only older context.
- [x] Persist summaries with source ranges, versioning and regeneration rules.
- [x] Tell the user when older context was compacted.
- [x] Add tests for ordering, owner isolation and deterministic context
  selection. Malformed model-summary output is not applicable because the first
  compaction algorithm is deterministic and does not invoke a model.
- [x] Persist a visibly stopped partial assistant response through the new
  authoritative turn contract.

## Then: Explicit personal memory

- [x] Record an ADR for personal-memory consent, sensitivity and ownership.
- [x] Add a profile-level opt-in with German and English explanations.
- [x] Support an explicit “remember this” request as the first extraction path.
- [x] Require confirmation before retaining sensitive memories such as religion,
  health, relationships or political beliefs.
- [x] Add a profile view to inspect, correct and forget individual memories.
- [x] Retrieve only a small relevant set and make memory influence visible.
- [x] Keep memory records separate from conversation history and executable
  plugin authority.

## Security and operations follow-up

- [ ] Add login throttling and temporary backoff before remote exposure.
- [ ] Add active-session listing and selective session revocation to the profile.
- [ ] Define conversation and activity retention policies.
- [ ] Define personal-memory retention expiry and archival policy.
- [ ] Add activity actor scoping and tamper evidence before making compliance
  claims.
- [ ] Add backup and restore verification for PostgreSQL data.

## Next vertical slice: Velora device control through Core

Current planning checkpoint: implementation may continue on the software-only
items below while physical Nanoleaf verification is deferred until the owner
completes physical testing. The market and user-needs analysis now prioritises
Kyrion's trustworthy orchestration and operations layer over raw integration
breadth, without bypassing Core authority or the local-first boundary. See
[Product Strategy](../product-strategy.md).

- [x] Add the first bounded German and English proposal schema for room-scoped
  Nanoleaf power and brightness commands.
- [x] Resolve exact owner-visible room names in Core and apply a command to all
  matching owner-scoped Nanoleaf connections without an unnecessary follow-up.
- [x] Return and persist deterministic text/Voice Mode feedback derived from
  the Core execution result rather than model-generated success claims.
- [x] Reject descriptive questions and out-of-range brightness values instead
  of treating them as executable commands.
- [x] Expose an owner-scoped Core runtime catalog containing safe device, room
  and capability metadata without provider hosts or credentials.
- [x] Supply the runtime catalog to the AI service and suppress proposals for
  capabilities that are not currently available to the owner.
- [x] Define provider-neutral `online`, `offline`, `degraded` and `unknown`
  availability with an optional observation timestamp; report `unknown` until
  Core has a real sufficiently recent observation.
- [x] Refuse device-specific qualifiers in the initial room-wide parser instead
  of silently discarding them and controlling every device in the room.
- [x] Persist the latest owner-scoped device observation through Flyway V10.
- [x] Add a CSRF-protected explicit refresh capped at 20 devices; keep catalog
  reads side-effect free and expire observations to `unknown` after 60 seconds.
- [x] Connect Home to passive catalog reads and a visible German/English status
  refresh with unknown, online, offline, degraded and last-observed display.
- [x] Persist availability observations from Velora command outcomes without
  allowing secondary observation-storage failure to falsify command results.
- [x] Add exact owner-scoped stable-device selectors and move Home quick-power
  actions onto the same provider-neutral Core command path as Velora.
- [x] Let Velora address one device by an exact, unique catalog display name;
  pass only its stable owner-scoped ID to Core and refuse partial or duplicate
  name matches instead of guessing.
- [ ] Define provider-neutral device identity, state, capability, command and
  command-result contracts above the working Nanoleaf implementation.
- [ ] Expose an owner-scoped Core inventory that can resolve devices by stable
  ID and natural-language selectors such as room, display name and capability.
- [x] Define a bounded tool catalogue from the capabilities currently available
  to the authenticated owner; do not give the AI service provider credentials
  or arbitrary network access.
- [x] Let Velora propose typed commands while keeping target resolution,
  argument validation and execution authoritative in Core.
- [ ] Add explicit clarification UX for plausible ambiguous rooms or devices;
  the current exact-name slice safely refuses duplicate, partial and invented
  device names without executing them.
- [ ] Define permission and confirmation policy for routine, destructive,
  costly, privacy-sensitive and safety-relevant capabilities.
- [x] Execute accepted proposals through the same integration command path used
  by Web controls and return a typed result to text and voice conversations.
- [ ] Record proposed, rejected, confirmation-required and executed actions with
  actor, source and one correlation identifier without logging private prompts
  or secrets.
- [ ] Prove the first end-to-end action with German and English requests to turn
  on the existing Nanoleaf devices in the living room.
- [ ] Add tests for successful execution, ambiguity, missing capability,
  unavailable devices, cross-owner access, malformed model output and adapter
  failure.

Success criterion:

> An authenticated owner can ask Velora by text or browser-backed voice to turn
> on the Nanoleafs in the living room. Core resolves and validates the targets,
> executes through the Nanoleaf adapter, records the correlated outcome and
> returns an accurate result without exposing credentials to Web or AI.

## Ordered gateway hardware preparation

- [x] Record the August 2026 Raspberry Pi, radio, voice and smart-home hardware
  order in the [Development Hardware Roadmap](../hardware-roadmap.md).
- [x] Define and implement authenticated gateway registration, identity,
  heartbeat and health
  contracts before implementing radio-specific control.
- [x] Separate heartbeat-reported Zigbee candidates from owner-approved Home
  devices in the first UI slice; require an explicit name and Add action before
  Core creates or reconciles the stable inventory record.
- [ ] Apply the same post-approval contract to Zigbee, Thread/Matter,
  Bluetooth, local-network and future adapter discovery: create or reconcile a
  stable database device record, display it automatically on `/home`, and
  persist every room assignment, rename and removal lifecycle change.
- [x] Define stable USB adapter identity/configuration without assuming device
  paths before the Raspberry Pi and radios are available.
- [ ] Prepare provider-neutral Integration Manager, Device Manager, discovery
  inbox and gateway/voice-satellite health views in German and English.
- [ ] Complete hardware acceptance: Raspberry Pi, Sonoff ZBDongle-E and USB
  voice hardware baseline validation is complete; ZBT-2 and recovery drills
  remain.
- [x] Expose the first stable owner-scoped Zigbee light capabilities and typed,
  audited device commands in Web through Core.
- [x] Replace automatic post-pairing import with a Core-owned Zigbee discovery
  inbox and explicit approve, name, remove and re-pair lifecycle. Rejection of
  a discovered-but-unapproved candidate remains a small UX follow-up.
- [ ] Harden the implemented asynchronous Zigbee command-status contract and
  visible pending/failure UI; test ownership, timeout, malformed
  payload, adapter failure, retry and idempotency boundaries.
- [x] Separate fast 250 ms gateway command polling from the five-second health
  heartbeat and add a Home entry point for explicit Zigbee or local-network
  device discovery. The first asynchronous command-status slice is implemented.
- [ ] Prove Zigbee, Matter-over-Thread, Wi-Fi and voice support as separate
  end-to-end slices; do not mark an integration complete based only on pairing
  or discovery.

### Deferred gateway productisation

The current SSH, `sudo`, firewall and command-line provisioning flow is an
intentional development path, not the finished owner experience. Do not pause
protocol validation to generalise it prematurely. After the planned gateway
integrations work end to end:

- [ ] Replace developer provisioning with a guided German/English Web
  onboarding flow that requires no programming or terminal knowledge.
- [ ] Package the gateway agent with installation, update, rollback and clean
  removal support.
- [ ] Add automatic local discovery, understandable physical confirmation and
  a discovery inbox that separates detected candidates from approved devices.
- [ ] Add guided Zigbee, Thread/Matter, Bluetooth and voice setup with safe
  permissions, restore points and translated diagnostics.
- [ ] Reset the development Raspberry Pi and perform a complete clean-room
  onboarding test as a new owner would, recording every manual prerequisite,
  failure and recovery step.
- [ ] Do not call gateway onboarding product-ready until that clean-room test
  succeeds without SSH, manual firewall editing or copied terminal commands.

## Current open-work grouping

### Implementable now

- [ ] Stabilise the provider-neutral device and capability contracts.
- [ ] Centralise stable-ID, exact-room, exact-name and capability target
  resolution in a Core-owned Device Manager.
- [ ] Introduce households, members and initial owner/member/guest roles above
  the current single-owner foundation.
- [ ] Define action permission and confirmation classes.
- [ ] Implement Observe, Control and Manage integration profiles as presets over
  granular permissions, including immediate reduction and confirmed elevation.
- [ ] Audit proposed, rejected, confirmation-required and executed actions with
  actor, source and correlation ID, without storing private prompts.
- [ ] Define integration-health reason codes and user-facing diagnostic
  explanations.
- [ ] Add a Home Assistant adapter that maps bounded devices, areas, state,
  capabilities and health into Kyrion-owned contracts and enforces the selected
  Observe, Control or Manage profile.
- [ ] Implement pre-change restore-point orchestration before integration
  onboarding, permission elevation and material device lifecycle operations.
- [ ] Add a Core restore-point manifest with `complete`, `partial`,
  `unsupported` and `failed` coverage plus separate restore-verification state.
- [ ] Add backup-provider adapters for Core/PostgreSQL, Home Assistant, gateway
  configuration and supported Zigbee/Thread infrastructure.
- [ ] Block protected changes after required backup failure and present exact
  unsupported coverage before any limited owner-approved operation.
- [ ] Add checkpoint retention, deduplication, integrity checks, storage quotas
  and scheduled real restore exercises.
- [ ] Preserve HA identities and automation provenance; classify migrations as
  full, partial or unsupported and never silently delete source data.
- [ ] Add a clarification response and continuation flow for ambiguous targets.
- [ ] Complete boundary tests for ambiguity, missing capability, unavailable
  devices, cross-owner access, malformed AI output and adapter failure.
- [ ] Prepare German and English Device Manager, Integration Manager, discovery
  inbox and gateway/voice-satellite health views.

### Awaiting owner verification

- [x] Physically verify fresh authentication and Home quick-power actions
  against the existing Nanoleaf devices.
- [ ] Repeat the German Velora text command after the unique `room`/`raum` alias
  and contextual room-correction fix, then verify brightness, English and Voice
  Mode commands.
- [ ] Physically verify explicit status refresh and truthful
  unavailable-controller feedback.

### Physical gateway and hardware validation

- [x] Validate the Raspberry Pi 5 host, storage, Ethernet, IPv6, temperature,
  throttling and integrated Bluetooth inventory.
- [x] Validate the Sonoff ZBDongle-E and first Philips Hue colour lamp through
  real pairing, state reporting and reversible Web commands.
- [x] Pair a second Philips Hue colour lamp, verify automatic Core database and
  `/home` import, and configure both lamps to recover their last state after a
  cold power cycle.
- [x] Validate the Delock USB microphone and Pebble V3 Bluetooth playback,
  including temporary capture, direct/browser playback, reboot reconnect and
  bounded authenticated gateway health.
- [ ] Validate the Home Assistant Connect ZBT-2 after attaching it.
- [ ] Prove gateway registration, heartbeat, restart and temporary-network-loss
  behaviour on the real Raspberry Pi node. Registration, repeated heartbeat
  and agent-service restart are proven; Pi reboot and network-loss recovery
  remain open.
- [ ] Accept Zigbee, Matter-over-Thread, Wi-Fi, Bluetooth and voice independently
  through recorded end-to-end results.

This grouping is a status view over the authoritative tasks above and does not
create duplicate scope. The priority order reflects the recorded market and
user-needs analysis: trust foundation, daily usability, then differentiation.

## Later product slices

- [ ] Add the future three-mode AI product choice: Kyrion Local, Kyrion Managed
  AI and Bring Your Own AI, all using the same provider-neutral contracts.
- [ ] Detect and benchmark CPU, RAM and VRAM, then recommend transparent local
  profiles such as CPU-only, Local Lite, Local Standard and Local Performance.
- [ ] Let Expert Mode route STT, LLM and TTS independently; keep Simple Mode to
  understandable Local, Managed or External choices.
- [ ] Before building Kyrion Managed AI, decide data minimisation, residency,
  retention, consent, billing, quotas, availability and operational support.
- [ ] Implement and validate a bounded external-provider plugin only after the
  provider contract, secret handling, permissions, data-flow disclosure and
  audit boundaries are stable.
- [x] Add an official internal Plugins catalog and Nanoleaf detail page.
- [x] Discover Nanoleaf controllers through mDNS with a manual private-IPv4 fallback.
- [x] Persist owner-specific connections and AES-GCM-encrypted credentials in Core.
- [x] Add editable persistent device names and confirmed connection removal.
- [x] Control power, brightness, colour, colour temperature and stored scenes.
- [x] Show controller-derived palette previews for compatible scenes.
- [x] Add owner-specific rooms and persistent device assignments.
- [x] Replace the Home placeholder with live room/device cards, quick actions
  and detailed controller dialogs.
- [ ] Add bounded background status refresh or device events.
- [ ] Reconcile connections automatically after DHCP address changes.
- [ ] Revoke physical-controller tokens when removing reachable connections.
- [ ] Add focused Core HTTP integration tests for room ownership, cross-owner
  assignment rejection and Nanoleaf command validation.
- [ ] Complete a responsive German/English visual pass for Plugins and Home in
  both themes.
- [ ] Replace browser speech providers only after explicitly selecting suitable
  local STT and TTS runtimes.

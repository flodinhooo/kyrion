# Voice and Action MVP TODO

Status date: 2026-08-12

This checklist is the execution view of the
[Voice and Action MVP plan](2026-08-12-voice-action-mvp-plan.md). It does not
replace the repository-wide [`TODO.md`](TODO.md). Later evidence should update
both without marking planned work as implemented.

## Phase A — Voice assets

Checkpoint 2026-08-19: the owner listened to and approved a 30-line German
Qwen3-TTS 1.7B voice-clone selection derived from the checksum-verified
immutable `velora-f` reference. Six entries matching the existing bilingual
Core Fixed catalog (two greetings, two farewells and two acknowledgements) are
registered in the production manifest. The other 24 approved German WAVs
remain outside Git as reviewed expansion inventory until their typed outcome
resolvers and English counterparts exist. The six English MVP assets remain
pending, so Phase A and Raspberry Pi acceptance are not complete.

- [ ] Install Audacity for local Windows recording and editing.
- [ ] Install Seed-VC in an isolated Python 3.10 environment outside the Kyrion
  runtime and repository.
- [ ] Record exact Seed-VC source, checkpoint, version, checksum and licences.
- [ ] Create the private `velora-mvp-v1` raw/clean/converted/reviewed directory
  structure outside Git.
- [ ] Freeze the first 28-asset DE/EN catalog and exact wording.
- [ ] Add the new pending response entries only after wording review.
- [ ] Record at least four takes per line and retain every raw session.
- [ ] Select and conservatively clean the source takes without overwriting raw
  audio.
- [ ] Run a six-phrase Seed-VC pilot covering short endings, umlauts, plosives,
  questions and English.
- [ ] Compare unconverted and converted candidates without provider labels.
- [ ] Decide whether zero-shot Seed-VC is sufficient; do not begin RVC training
  without a suitable target dataset and an explicit decision.
- [ ] Convert the complete catalog only after the pilot passes.
- [ ] Master approved candidates consistently and export mono PCM16 24 kHz WAV.
- [ ] Listen to every complete final WAV for wording, termination, identity,
  artifacts, loudness and silence.
- [ ] Register files one by one using
  `.run/register_fixed_voice_response_asset.py` only after owner approval.
- [ ] Verify all manifest hashes and document any intentionally pending assets.

## Phase B — Architecture decision

- [x] Record an ADR for the Core-owned Action Orchestrator and domain handler
  boundary.
- [x] Define `ActionContext`, typed `ActionProposal`, `ActionDecision` and
  `ActionOutcome` without untyped provider payloads.
- [x] Define `read`, `routine`, `confirmation_required`, `restricted` and
  `forbidden` policy classes.
- [x] Represent Web, Voice, Mobile, Automation and Integration as explicit
  interaction channels.
- [x] Define stable machine-readable result and denial codes.
- [x] Specify correlation and idempotency identity across proposal, decision,
  execution and response.

The accepted foundation is recorded in
[ADR 0011](../adr/0011-core-owned-action-orchestration.md). The authenticated
Web endpoint now persists owner-scoped idempotency claims and completed typed
outcomes; mismatched or still-running replays are rejected.

## Phase B — Room semantics

- [x] Add the bounded `RoomType` enum and lowercase wire values.
- [x] Add a Flyway migration with `room_type = 'other'` for existing rooms.
- [x] Extend Room repository and HTTP contracts. Owner-scoped repository
  integration remains covered by the full PostgreSQL/Testcontainers run.
- [x] Extend the device catalog room projection with `roomType`.
- [x] Add German and English Room Type labels to locale resources.
- [x] Add Room Type selection to room creation/editing without making it
  prominent on ordinary Home cards.
- [x] Implement deterministic room-name normalization.
- [x] Implement localized `RoomType` synonyms in Core.
- [x] Resolve exact display name before semantic category.
- [x] Return ambiguity when more than one owner room matches a category.
- [x] Return not found instead of guessing.
- [x] Defer owner aliases to a separate table and follow-up slice.

## Phase B — Shared Core action path

- [x] Add the Core `ActionOrchestrator`.
- [x] Add the initial typed `DeviceActionProposal`.
- [x] Add `DeviceActionHandler` above the existing `DeviceCommandService`.
- [x] Let Core load the authoritative owner device/capability catalog.
- [x] Let the AI service propose only against the bounded supplied catalog.
- [x] Revalidate proposal type, owner scope, target, capability and arguments in
  Core.
- [ ] Apply explicit Voice-channel permission rules before execution. Routine
  actions currently pass through the shared policy service with a typed Voice
  context; per-action channel restrictions remain follow-up work.
- [x] Return one correlated `ActionOutcome` from the real domain result.
- [x] Record proposed, rejected, confirmation-required, executed and failed
  states without prompt or credential leakage.
- [x] Add a Core action endpoint for authenticated Web clients.
- [x] Remove device proposal, execution and result wording from the Next.js chat
  route after the Core endpoint passes tests.
- [x] Route browser chat/Voice Mode through the new Core path.
- [x] Route the physical Voice dialogue through the same orchestrator directly.
- [x] Preserve ordinary Dynamic dialogue when no valid Action Proposal exists.
- [x] Resolve bounded German and English multi-room light power commands into
  one Core-validated proposal. Every named room must resolve uniquely before
  execution; unknown, ambiguous or duplicate rooms execute nothing.

## Phase B — Voice result policy

- [ ] Add typed outcomes and catalog resolvers for `target.not_found`,
  `target.ambiguous`, `device.offline` and `action.denied`.
- [ ] Add generic Fixed `command.succeeded` and `command.failed` variants while
  retaining target-specific Template responses.
- [x] Prevent `command.succeeded` unless a complete successful result is
  confirmed.
- [ ] Treat partial success as a separate Template outcome.
- [x] Do not play `dialogue.acknowledged` before command execution.
- [ ] Use silence or a semantically neutral earcon if processing feedback is
  later required.
- [x] Ensure cancelled or stale turns cannot execute after proposal or emit
  queued result audio.

## Phase C — First physical command

- [ ] Configure one room with a visible name and `roomType = office`.
- [ ] Verify that German `Büro` resolves to that room only when unique.
- [ ] Limit the first proposal contract to Nanoleaf `power.set`.
- [ ] Run `Hey Velora, mach das Licht im Büro an.` through the physical Pi.
- [ ] Confirm exactly one proposal and one adapter execution.
- [ ] Confirm the physical Nanoleaf changes state.
- [ ] Confirm the spoken success follows the real `DeviceCommandResult`.
- [ ] Confirm session, turn and action correlation IDs remain aligned.
- [ ] Add the corresponding automated Core, AI and Satellite regression tests.

## Phase D — Reliability

- [ ] Complete at least twenty consecutive physical success repetitions.
- [ ] Verify no duplicate command or duplicate playback.
- [ ] Verify no command or audio survives a cancelled/closed session.
- [ ] Verify timeout never produces success speech.
- [ ] Verify adapter failure never produces success speech.
- [ ] Verify an offline device selects the truthful offline response.
- [ ] Verify unknown target performs no execution.
- [ ] Verify ambiguous target performs no execution.
- [ ] Verify malformed AI output is rejected in Core.
- [ ] Verify cross-owner targets are inaccessible.
- [ ] Record physical timestamps and outcomes without storing room audio.

## Phase E — Hardware and integrations

- [ ] Reuse the accepted action path for Zigbee Hue power.
- [ ] Add brightness only after power reliability passes.
- [ ] Harden Zigbee async timeout, retry and idempotency boundaries.
- [ ] Add Sonoff button events as a bounded event slice.
- [ ] Add Sonoff motion events as a bounded event slice.
- [ ] Attach and validate Home Assistant Connect ZBT-2 as a dedicated Thread
  radio.
- [ ] Establish OTBR/Thread commissioning and recovery evidence.
- [ ] Integrate Aqara Door and Window Sensor P2 contact events through Matter
  over Thread.
- [ ] Integrate Shelly H&T Gen3 temperature/humidity observations.
- [ ] Integrate myStrom WiFi Switch 2 power and energy capabilities.
- [ ] Validate Bluetooth discovery as a separate least-privilege slice.
- [ ] Record Pi reboot and temporary-network-loss recovery.

## Raspberry Pi runtime cleanup

- [x] Confirm no experimental TTS or PCM debug server is active on the Pi.
- [x] Confirm the active Voice path uses the batch Satellite runtime.
- [ ] Document current system and user service inventories as an operational
  checkpoint.
- [ ] Confirm whether AnyDesk remains required; otherwise disable it reversibly.
- [ ] Confirm whether a graphical desktop remains required; otherwise disable
  LightDM/Xorg/LXDE startup reversibly.
- [ ] Disable CUPS if no printer functionality is required.
- [ ] Disable RPC/NFS services only after confirming no required mounts use them.
- [ ] Review desktop portal, GVFS, MPRIS and VNC units after any headless change.
- [ ] Keep PipeWire, WirePlumber, Bluetooth and `filter-chain` until Pebble
  playback is proven without each candidate.
- [ ] Reboot and rerun gateway heartbeat, wake word, capture and playback checks
  after cleanup.
- [ ] Document enable/rollback commands for every changed unit.

## Later domains — contracts only for now

- [ ] Preserve typed extension points for Calendar actions.
- [ ] Preserve typed extension points for Email draft/send actions.
- [ ] Preserve source-scoped read policy for Local Search.
- [ ] Keep Spotify and YouTube content resolution domain-specific.
- [ ] Define Playback as a separate target/execution capability reusable by
  Spotify, YouTube and local media.
- [ ] Route Automation actions through the same policy and audit boundary.
- [ ] Do not implement speculative domain adapters as part of the first Device
  Action slice.

## Deferred until after the MVP

- [ ] Train or commission a final custom Velora TTS voice.
- [ ] Reassess Dynamic TTS only after the product action paths work.
- [ ] Add streaming TTS and reliable barge-in.
- [ ] Add owner-managed room aliases and clarification continuations.
- [ ] Add the optional Home Assistant adapter without making it Core.
- [ ] Redesign the Web information architecture so Home represents Kyrion as a
  personal local platform rather than a generic chat application.

## Public repository preparation

- [x] Rewrite the root README to distinguish implemented, experimental and
  planned functionality.
- [x] Link the focused Voice/Action MVP plan and dated checklist.
- [ ] Select and add an actual open-source `LICENSE` before describing reuse as
  legally permitted.
- [ ] Add contribution guidelines and a code of conduct if external
  contributions are invited.
- [ ] Perform a full tracked-history secret and private-data audit before making
  the repository public.
- [ ] Review committed development hostnames, private LAN addresses and personal
  usernames for portfolio publication even where they are not credentials.
- [ ] Confirm all third-party model, dataset, voice-reference and generated
  asset licences/provenance before distributing those artifacts.

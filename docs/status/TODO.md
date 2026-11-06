# Kyrion Development TODO

Current Home product slice: [family calendar plan](../home-family-calendar-plan.md),
with owner-confirmed joint editing and [ADR 0035](../adr/0035-home-membership-and-family-calendar-direction.md).
The [two-chat assignment](../agent-handoffs/2026-11-06-parallel-home-and-gateway.md)
separates Home/Calendar work from Gateway authority, including shared-file,
migration and Git/build coordination. Both assignments were started explicitly by
the owner and implemented on master without creating additional worktrees.

Parallel source work has now been implemented and jointly verified: **370 Core
tests**, zero failures/errors/skips, plus bootJar; Web **211 tests**, ESLint,
TypeScript and production build. Recorded Core before/after source hashes match.
See [Home results](../agent-handoffs/2026-11-06-home-calendar-results.md) and
[Gateway results](../agent-handoffs/2026-11-06-gateway-authority-results.md).
V42/V43 and the new runtime behavior have **not** been deployed.

- [x] HOME-01/02 native slice: explicit participant selection, jointly editable
  Kyrion household events, revision conflicts, creator-only deletion, person
  display filter, transactional audit and DE/EN UI. Legacy local/Google behavior retained.
- [ ] HOME-03: voluntary personal calendar visibility grants and Core-enforced
  private/availability/details views; ownership is not implied by installation roles.
- [ ] HOME-04: explicit participant provider destinations and owner-approved
  writes, per-target status, idempotent retries and conflict handling.
- [ ] Coordinate data-safe runtime rollout and real browser/household acceptance.
  Gateway V42 requires explicit re-saving of historical button grants; legacy
  pending commands must not acquire inferred authority during rollout.

Current integration checkpoint: [master consolidation and worktree closeout](2026-11-06-master-worktree-closeout.md).
Development continues on `master`; all four former worktree histories are integrated
and no secondary worktree remains registered. The [Pi V41 activation](2026-11-06-pi-update-activation.md)
supersedes the earlier V30 activation blocker. Historical handoff integration
checkboxes below must not be interpreted as missing source changes. Remaining
security and physical/release acceptance work is tracked in the closeout.

- [x] Consolidate every former worktree branch tip on master, preserve open Calendar/HA work, and remove accidental gitlinks and active secondary worktrees.
- [x] Cancel silent AI HTTP requests when captured session/permission/route/Knowledge authority is revoked; test both missing headers and incomplete events.
- [x] Revalidate queued button bindings; test deleted, reconfigured and unchanged bindings.
- [x] Verify the consolidated source: Core332, Web200, AI172; builds and configured static checks pass.
- [x] Persist originating human/capability authority through Gateway queue/claim
  and define explicit automation grants: implemented and tested in Assignment B;
  live rollout/physical acceptance remains separate.
- [ ] Complete optional-context opt-out/content, multi-process worker/cache/stream lifecycle certification; retain the single-Space/Business Voice guards.

Latest active fix: [empty recognition local V39 rollout](2026-10-31-voice-no-speech-rollout.md).
- [x] Activate explicit terminal no_speech/inactivity closure on master/V39 and installed batch client; no model/action/TTS/usage for blank input, no retry or double close.
- [x] Full Core315/296, Satellite77 and lint/build checks; actual Pi blank-audio close plus complete normal local-model/Chatterbox playback and single usage attempt verified. Schema39 and guards retained.
- [ ] Owner repeats both live questions, stays quiet10s, wakes again; verify no empty-STT exception. Inactivity ending is still silent; no spoken barge-in added.

Latest physical run: [live dialogue log diagnosis](2026-10-31-velora-live-log-analysis.md).
- [x] Correlate two actual wakes, three completed response turns and two subsequent empty-STT failures; owner reports convincing audible output. Both sessions are closed with reason error, Satellite remains active without restart.
- [x] Handle empty STT as explicit no_speech closure; retain no-invocation/no-usage behavior and V39 compatibility. Acoustic cause of brief post-playback VAD triggers remains unproven.
- [ ] Define/verify clear session-end feedback and complete physical end-piece/pause acceptance; current inactivity close is silent and both live attempts ended through the error path.

Latest hearing-review preparation: [A/B pack, local STT and anomaly findings](2026-10-31-tts-listening-review.md).
- [x] Map all24 existing WAVs to identical expected inputs, configuration, run/seed and SHA256; retain a committed synthetic audit.
- [x] Inspect termination and pure text preparation; no frame/token hard limit reached and no input-content truncation found. No proven engine defect, so no parameter change or new synthesis.
- [x] Analyze quiet energy and transcribe all samples locally:20.48s includes16.90s below−40dBFS;2.80s list recognizes only item1; first-warm list also lacks item3 in STT. STT is diagnostic, not hearing acceptance.
- [x] Prepare fixed-first-warm blind A/B page, DE/EN labels, ratings export, reveal/times and all24 runs; verify browser playback/served hashes without claiming audibility.
- [x] Human A/B pair decision received: Chatterbox preferred in all three texts (A/B/A); selected MOSS list completeness1/5. Retain Chatterbox, do not promote this MOSS configuration. Separate hearing observations for both outliers were not supplied; no further automatic tuning round.
- [ ] Two Hey Velora dialogues and acoustic/end-piece/pause review; operator cancellation commands are documented, spoken barge-in is absent. Gateway/host/cloud/V40 remain separate.

Latest bounded TTS decision: [isolated CPU candidate and active-path preservation](2026-10-31-isolated-tts-decision.md).
- [x] Inventory installed engines/hardware; compare exactly one existing MOSS CPU candidate with resident Chatterbox, three fixed German texts and three warm runs per text; keep cold/first-use boundaries explicit.
- [x] Retain active V39/schema39/voice, guarded pin and rollback; verify seven services, Pi health/authentication and clean session closure.
- [x] Attribute2793ms section gap to next synthesis exceeding preceding audio; existing overlap is already active, so no speculative concurrency change.
- [ ] Human review of retained MOSS samples, especially suspicious2.80s list and20.48s two-sentence outputs; faster batch medians do not establish acceptable or complete speech. No activation or further tuning before this review.
- [ ] Twice Hey Velora, heard answer/section continuity and same-clock acoustic timing. Spoken interruption is not implemented; technical abort is a different check.
- [ ] True Chatterbox model-cold comparison was intentionally not performed; resident fallback was preserved. Gateway, host restart, cloud and V40 remain separate gates.

Latest Voice continuation: [section boundaries, engine limits and playback safety](2026-10-31-voice-section-boundary.md).
- [x] Release complete list items with their first meaningful content; keep the final item,32-character minimum and8-section cap.
- [x] Measure T3/decoder/packaging and per-section text/audio lengths; selected Chatterbox0.1.7 remains a batch engine.
- [x] Activate bounded TTS HTTP pooling, later-stream error handling and matching V39/master Core fixes.
- [x] Compare three identical digital questions before/after; verify TTS/playback interruption, actual second-section503, recovery and single usage entries.
- [ ] Gapless playback is not accepted: a recovery run had2793ms between player processes. Human word endings, continuity, wake and acoustic latency remain open.
- [ ] Spoken barge-in is not supported by the current synchronous batch path; engine-bound first-section latency remains above three seconds.
- [ ] Privileged Gateway destination/heartbeat diagnosis and a safe full-host restart remain separate operational gates.

Latest Voice performance work: [latency evidence and local activation](2026-10-31-voice-latency.md).
- [x] Trace upload, STT, context, first provider delta, stream publication, TTS queue/compute and Pi receipt using correlated process-local monotonic timing.
- [x] Activate servlet framing/flush correction and ordered sentence TTS on a V39-compatible artifact; keep the model/voice, auth, budgets and schema unchanged.
- [x] Verify a model-cold run, three comparable warm runs, valid answer playback, single usage settlement and controlled abort/reconnection.
- [x] Guard against telemetry disconnects leaking uninvoked reservations, with full Core regression checks.
- [ ] Under-three-second first-answer latency is not achieved; selected batch TTS remains the main measured limit.
- [ ] Human wake, heard answer quality and sentence continuity; privileged Gateway target/heartbeat diagnosis and full-host cold-start proof remain open.

Latest authorized local rollout: [V39 Voice activation and digital dialogs](2026-10-31-velora-local-rollout.md).
- [x] Activate the HTTP/1.1 fix in a clean pre-V40 Core artifact; retain schema39 and guarded hash pin.
- [x] Install bounded IPv4-first Satellite dialing with a rollback backup and unchanged credentials/config.
- [x] Complete two German digital STT/Gemma/TTS/Pi playback turns, persist usage once each, close sessions and verify idle reconnect without extra usage.
- [x] Reload the helper and prove it restarts the pinned Core; recover its interrupted AI/STT/TTS children and verify all seven services.
- [ ] Human wake word, two audible dialogs and acoustic latency/quality.
- [ ] Privileged Gateway configuration diagnosis: journal success does not match this Core's stale heartbeat.
- [ ] Investigate delayed Pi stream-event delivery; isolate helper child lifetime; full host cold-start proof.
- [ ] Separately authorize V40 migration and real cloud spending/acceptance.

The earlier October31 report below is historical; its inactive-fix statements are superseded.

Latest Pi/Velora work: [October31 guarded LAN repair and partial hardware results](2026-10-31-pi-velora-acceptance.md).
Pi IPv4/Core health/authenticated sessions and a same-artifact guarded restart
are verified. Physical capture works; full Voice is blocked by runtime h2c/IPv6
compatibility fixes that are prepared but not deployed, plus on-site acoustic
observation. [V40 rollout](../v40-rollout.md) is rehearsed with isolated synthetic
dump/restore only; active V39 and cloud-spending boundaries remain intact.

Current K-AI accounting/acceptance continuation:
[durable accounting follow-up](2026-10-31-kai-accounting.md) and
[operator investigation / Cloud / Velora checklists](../kai-accounting-and-acceptance.md).
KAI-005 software hardening is verified separately from provider billing lookup,
real cloud acceptance, physical Voice and deployment of additive V40.

Latest K-AI follow-up: [October 31 accounting and runtime checks](2026-10-31-kai-resume.md).
The [combined integration](../integration/final-integration-report.md) supersedes
the original handoff's failing software baseline; the local database's verified
[V39 upgrade](../integration/database-upgrade-v39.md) also supersedes its V33 state.
K-AI M01–M03 are implemented; live cloud, physical Voice and the remaining
reconciliation/isolation acceptance gates remain separate.

Current checkpoint: [2026-10-30 stabilization](2026-10-30-stabilization.md).
Calendar/HA recovery is integrated and automatically verified. Remaining near-term
work is controlled rollout/full-host cold-start acceptance, authenticated Calendar/
Google acceptance and physical device/voice reliability. The
[multi-provider architecture review](2026-10-30-ai-architecture-review.md) is
historical analysis; subsequent [provider support](../ai-model-providers.md)
is implemented with simulated cloud acceptance, not real account acceptance.

Last updated: 2026-10-12.

This is the consolidated active backlog. Source of truth: current code,
the [hardening closeout](2026-10-11-security-hardening.md), the
September 14/15 closeouts and the [Installer readiness review](2026-10-11-installer-readiness.md).
A checkbox means implemented/tested only to the extent stated; it never implies
new deployment or physical acceptance. The prior mixed/historical list is
preserved byte-for-byte in [the historical snapshot](TODO-history-before-2026-10-11.md).
Historical unchecked experiments are not the current work order.

## Completed foundations, with bounded evidence

- [x] Core-owned authentication, invitations, installation-wide RBAC, protected
  OWNER role and member deactivation are present. September 14 records Pi
  deployment; current HTTP regressions cover primary-owner protection and
  deactivation/session revocation. Security hardening and its remaining operational limits are recorded below.
- [x] Calendar authentication interceptor registration is fixed. Local CRUD and
  combined local/read-only Google display exist. Current tests cover missing/explicit optional fields, permissions and
  the
  Web creation payload and workspace-scoped Core CRUD; live browser UX remains open.
- [x] Shared Core Action Orchestrator, exact target resolution, initial policy
  classes, owner-scoped audit integrity and Activity inspector are implemented.
- [x] Bounded read-only HA import, stable identities, basic state and room mapping
  exist. Web probe/connect/disconnect and encrypted credential persistence are
  also present; old operator-only documentation has been corrected.
- [x] PostgreSQL backup and isolated SQL restore scripts, encrypted personal
  exports and auditable retention exist. These are not complete deployment recovery.
- [x] Always-on Pi platform Compose and migration/HTTPS scripts exist. They are
  developer-operated deployment tooling, not Installer v1 or a safe general updater.
- [x] Reproduce and fix YouTubeLinksTest constructor compilation failure; verify
  link preparation does not invoke gateway or command services.
- [x] Reproduce and fix member deactivation's PostgreSQL Instant binding error;
  verify revocation and reactivation/new login without reviving old sessions.
- [x] Run current Core/Web checks and infrastructure syntax/configuration checks;
  record exact results and limitations in the readiness review.
## Security hardening implemented and tested (2026-10-11)

See the [hardening closeout](2026-10-11-security-hardening.md); previous readiness
findings are retained as a historical baseline, not a current implementation status.

- [x] R1: Explicit Calendar CRUD permissions, service checks, workspace ownership,
  unmapped authenticated-route denial and USER/VIEWER/custom-role HTTP denials.
- [x] R2: Registration uses existing roles without seeding; fresh role defaults
  never replenish existing grants. Parallel invitations preserve revoked rights.
- [x] R3: Actual actor and workspace are separate. Delegates have permission ceilings,
  self-change and OWNER protections; actual actor/target is audited.
- [x] R4: RBAC, identity/session changes, registration and local Calendar changes
  include audit in transactions; workspace locks serialize authorization/mutation.
  Audit failure, rollback and concurrent permission-revocation regressions exist.
- [x] R5: Protected file bootstrap, 30-minute expiry, bounded throttling, global
  owner lock and permanent V31 initialization marker; concurrent/reused/invalid
  claims, rollback/retry and V30 upgrade are tested.
- [x] R6: Local/Google calendar mutations and HTTP permission refusals are audited
  without event text or secrets; actor/target/correlation is retained.
- [x] R7: Local calendars explicitly remain shared workspace data. Google APIs and
  catalogue metadata use the linking identity, excluded from shared device data.
- [ ] Installer-only acceptance: protected bootstrap provisioning/private delivery,
  TLS and mount permissions; Windows ACL and Linux permissions must be exercised
  on the supported target. No real installation/hardware acceptance is claimed.
- [ ] External Google success followed by audit storage failure needs operator
  reconciliation from the retained proposed event; no distributed transaction exists.
- [ ] Existing orphan roles from the previous delegated-workspace bug require a
  deliberate operator review if present; no automatic deletion or reassignment.

## P1: Installer v1 sprint

Follow [the implementation plan](../installer-v1-plan.md) and accepted ADR 0022.
The initial fresh-install boundary is implemented under
`infrastructure/installer-v1`; pilot and release acceptance remain open.

- [x] Accept the bounded fresh-install ADR for implementation; pilot release gates remain open.
- [x] Implement read-only preflight plus repeated existing-state
  checks; refuse existing/stopped/partial installations, keys, DBs and symlink targets.
- [x] Implement the reproducible ARM64 bundle builder, manifest digest validation
  and detached Ed25519 signing/verification scripts. A public signed release is
  still open until a protected GitHub release run succeeds.
- [ ] Build a public, signed, immutable ARM64 release bundle containing all four
  runtime images and no developer DB, keys, provider secrets or private artifacts.
- [x] Add guarded GitHub Actions CI and a disabled release/signing workflow;
  workflow files are locally reviewed; live GitHub execution and release-environment acceptance remain open.
- [x] Document installer `.env` variables and provide a secret-free
  `infrastructure/installer-v1/.env.example`; generated `.env` files remain
  protected installation state.
- [x] Create runtime-only portable Compose/Caddy templates, validated hostname/IP,
  file-backed secrets, load-only Core keys and verified health dependencies.
- [x] Implement fresh provisioning, trusted local HTTPS template and bounded first-owner
  setup with German/English messages; Core/Web/device contracts stay authoritative.
- [x] Add stable failure codes, bounded timeouts, protected stage journal,
  redacted diagnostics and explicit safe resume; preserve persistent state on failure.
- [ ] Add scoped deployment backup and isolated restore verification covering
  database, original keys/configuration, RBAC, Calendar and audit integrity.
- [ ] Test clean supported Debian ARM64 install, AI offline, concurrency,
  interruptions, corrupt bundle, missing keys and existing-installation preservation.
- [ ] Perform independent clean-room/reference-host acceptance before pilot release;
  record hardware evidence separately and never use the existing owner Pi as a fixture.

## P2: Current functionality and physical acceptance

### Calendar and household

- [x] R8: Local calendar survives optional Google failures. Both upstream calendar
  requests are bounded by timeouts; provider errors remain distinct from empty data.
- [x] R9 API: Strict optional Booleans, timezone validation and bounded content;
  browser-local event editing and bilingual Calendar resources are implemented.
- [x] Explicit mapped Google synchronization with conditional writes, stable IDs,
  conflict preservation, durable deletion/retry state and optional leased scheduling.
- [x] Windows recovery: preserved historical V31 checksum, worktree configuration
  loading, immutable runtime artifacts and live HA refresh to existing records.
- [ ] Complete authenticated browser month/week/day and DST acceptance after login.
- [ ] Reauthorize the live Google connection (`invalid_grant`), then perform
  disposable-calendar write acceptance only with explicit authorization. See
  [Windows acceptance](2026-10-19-windows-live-acceptance.md) for evidence and gates.
- [ ] Define explicit household membership, personal/shared calendar scope and
  room/device-level permissions as a later bounded extension to RBAC V1.
- [ ] Resolve consumer OAuth ownership/callback design (proposed ADR 0021) separately;
  do not bundle common OAuth client secrets into the installer.

### Smart home, integrations and Lounge

- [ ] Physically verify HA/Shelly import, Web connection flow, exact-room mapping,
  repeated sync, offline transitions and recovery; direct Shelly remains experimental.
- [ ] Physically verify generic Nanoleaf colour, unavailable-controller reporting
  and gateway failure diagnosis. Check DHCP reconciliation/token removal separately.
- [ ] Retest Sonoff button single/double/long room actions and motion history over
  restart with recorded latency and multi-provider/partial-failure cases.
- [ ] Verify OA20 exact-device independence, brightness, reconnect and power-cycle
  drift; present last-command state honestly instead of measured live telemetry.
- [ ] Record real Pi reboot/network-loss recovery and independently close remaining
  Thread/Matter/Wi-Fi/radio acceptance; provisioning scripts alone are not acceptance.
- [ ] Verify Spotify Web playback on the live receiver and invited-account rights;
  scope remaining playback/search/Voice ducking actions through Core.
- [ ] Complete German/English responsive visual review of Home, Plugins, Activity,
  Calendar, Users and Roles in both themes.

### Velora

- [ ] Verify capture/VAD -> processing playback -> device action -> truthful final
  outcome order; record twenty physical attempts including offline/partial cases.
- [ ] Verify exact lamp selection, room brightness, explicit gratitude/session end
  and next wake word; complete English reviewed fixed audio.
- [ ] Add typed partial-success speech and harden failure audio and reconnect
  across Core restarts. Do not reopen general TTS provider discovery for this slice.

## Later bounded product work

- [ ] Safe existing-installation updater with verified backup, migration compatibility
  and tested rollback; separate from fresh Installer v1.
- [ ] Integration Observe/Control/Manage profiles and pre-change restore orchestration;
  HA control/services/migration remain outside the current read-only import.
- [ ] General automation editor over existing typed device/event/action contracts;
  button bindings and motion history are already implemented groundwork.
- [ ] Mobile-responsive installable Web experience; then small Expo app with
  authenticated connection, device status and quick actions. apps/mobile is empty
  scaffolding, not an existing app. Remote access is a separate security slice.
- [ ] Energy views/Solar Manager, understandable notifications and diagnostic export
  after installation and recovery have been proven.
- [ ] Local/managed/external AI choices, signed plugin lifecycle and later marketplace;
  no new model/provider/runtime is required for Installer v1.
- [ ] Select a repository licence and publish contribution guidance before public
  source/release distribution; review bundled runtime/model licences separately.

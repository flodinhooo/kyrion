# Kyrion Development TODO

Last updated: 2026-10-11.

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

Follow [the implementation plan](../installer-v1-plan.md) and proposed ADR 0022.
The initial fresh-install boundary is implemented under
`infrastructure/installer-v1`; pilot and release acceptance remain open.

- [ ] Accept the bounded fresh-install ADR before pilot release.
- [x] Implement read-only preflight plus repeated existing-state
  checks; refuse existing/stopped/partial installations, keys, DBs and symlink targets.
- [ ] Build a public, signed, immutable ARM64 release bundle containing all four
  runtime images and no developer DB, keys, provider secrets or private artifacts.
- [x] Add guarded GitHub Actions CI and a disabled release/signing workflow;
  live GitHub execution and release-environment acceptance remain open.
- [x] Create runtime-only portable Compose/Caddy templates, validated hostname/IP,
  file-backed secrets, load-only Core keys and verified health dependencies.
- [x] Implement fresh provisioning, trusted local HTTPS and bounded first-owner
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

- [x] R8: Local calendar survives thrown optional Google fetches; that request
  has a 10-second timeout and a regression. Local upstream timeout remains follow-up.
- [x] R9 API: Missing/null syncToGoogle defaults to false; strict Booleans,
  timezone validation and bounded description are implemented. Browser timezone/DST
  and bilingual Calendar UX below remain open.
- [ ] Review selected-date creation and event editing in the browser, especially
  UTC/local/DST conversion; move existing hardcoded German text to bilingual resources.
- [ ] Correct the sync checkbox's user promise: it currently persists intent but
  does not perform full sync. Define conflict/delete/retry/idempotency semantics
  before implementing optional bidirectional Google sync.
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

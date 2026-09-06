# Pre-Velora platform consolidation

Date: 2026-09-06. Baseline: `master`, `015b909` (matched remote `master` at
inspection). Changes remain in the working tree; no deployment or hardware
acceptance is implied.

The pre-existing staged/deleted compatibility pages, local platform Compose
changes and `2026-09-05-pi-platform-update.md` were preserved. Compose received
only the additional optional HA environment forwarding on top of the owner's
existing changes.

## Result and scope

| Area | Implemented result | Verification boundary |
| --- | --- | --- |
| HA import | Fixed read-only snapshot, stable owner/provider/device identity, names, hardware labels, basic power/sensors and existing-room mapping | Automated fixtures and PostgreSQL; awaiting real HA/hardware |
| Health | Existing System services consolidated into healthy/degraded/offline/unknown, bounded reasons, real probe/heartbeat/sync timestamps | Automated contract and browser tests; no invented hardware signals |
| Device contracts | Read-only HA devices, preserved capability names, stale diagnostics, capability revalidation, generic Nanoleaf colour support | Core cross-provider and HTTP tests; colour change awaits physical acceptance |
| Action inspector | Existing audit correlation query, ordered stages, actor/source, duration, persisted outcome names/counts and failure reasons | Core/HTTP/contract tests and browser review |
| Hygiene | Private runtime artifacts and duplicate deployment archives preserved outside tracked paths; accidental empty file removed | Hash manifest and diff review |
| Documentation | README, status, TODO, roadmap, architecture and Shelly boundary reconciled | Documentation review; dated historical evidence retained |

**LLM proposes. Core decides. Adapter executes. Result confirms.** No new product
domain, HA control, automation, service calls, event subscriptions, TTS provider,
Matter/Thread work, mobile app or public plugin infrastructure was started.

## Home Assistant

The [import documentation](../home-assistant-import.md) describes configuration,
operation and limits. Core reads only its fixed `/api/template` request. Web and
Voice receive Kyrion UUIDs, capabilities and translated state, never HA entity IDs
or credentials. The token is configured only in the Core environment; it is not
copied into device persistence or the browser. An operator configures the HA URL,
token and owner UUID; Web then provides explicit import/sync.

Room names use trim and locale-independent case-insensitive equality. A unique
existing owner room is required; no match, absent area or ambiguous names produce
`null` (**Nicht zugeordnet / Unassigned**). No automatic room creation or fuzzy
matching occurs. Subsequent imports update names, room mappings, state and
availability without replacing the Kyrion UUID. A missing device remains unknown;
a failed HA request does not pretend every physical device is offline.

The snapshot covers registry-backed sensor, binary sensor, light and switch state
entities. Entity-only helpers and devices without those state entities are outside
this bounded import. Temperature, humidity, battery, occupancy and basic power
are read-only. Multiple conflicting numeric readings are omitted rather than
silently picked. Existing 60-second catalog freshness remains explicit.

**Shelly is not a fully working native Kyrion integration.** The direct RPC code
and its tests remain experimental; the selected sensor import path is HA. Neither
this statement nor the new import establishes full HA integration or physical
Shelly acceptance.

## Architecture and important corrections

- [ADR 0018](../adr/0018-read-only-home-assistant-import.md) records the bounded
  read-only import and its explicit HA-managed name/room reconciliation rule.
- Existing integration connections, owner rooms, observations and audit remain
  authoritative. Flyway V25 adds bounded imported sensor state and sync diagnostics,
  and makes stored `unknown` availability consistent with the public model.
- The import's PostgreSQL test found an existing nullable-room SQL parameter bug.
  `JdbcRoomRepository` now casts the null-room predicate to UUID, allowing an
  existing assignment to be cleared correctly.
- Existing `power.set`, `light.setBrightness` and `light.setColour` IDs are retained;
  no competing Web/Voice capability model or speculative rename was introduced.
  Generic Nanoleaf colour execution now matches its advertised capability. Core
  also validates numeric arguments and advertised capabilities at execution.
- The System services surface validates probe bodies and invalid configuration.
  Gateway child readiness expires with an offline/unknown parent. PostgreSQL uses
  a real Core query. Missing Voice/Zigbee/Spotify receiver observations remain
  unknown. No restart/update requirement or acoustic health is fabricated.
- V26 indexes the existing owner/correlation audit and action execution queries
  and retains parent action correlation on gateway commands. No second log store
  or audit integrity version is introduced.
- The inspector allowlists public event facts. Existing signed audit rows remain
  unchanged. A full action result is shown only when an existing persisted outcome
  exists. Adapter confirmation does not claim independently measured physical state.

See [Platform diagnostics](../platform-diagnostics.md) for the operational contract.

## Verification

Web: **77 tests passed** in 31 files; lint and the production build/type check
passed. Browser: **119 checks passed**, no unhandled exceptions, including the
expanded German/English mobile inspector. Core: **156 tests passed**, including PostgreSQL/HTTP integration tests; boot JAR
build passed. No open failures remain in these automated checks.

Earlier iterations found and corrected the HA mapper wiring, PostgreSQL timestamp binding, nullable
room predicate, stored unknown-availability constraint and a test matcher error.
Those failed iterations are not presented as successful verification.

- Core: `gradlew.bat test bootJar --console=plain`, including PostgreSQL 17
  Testcontainers, HTTP owner/authentication boundaries, HA import/reconciliation,
  persisted sync failures, action timeline and existing audit integrity tests.
- Web: `pnpm test`, `pnpm lint`, and `KYRION_BUILD_DIRECTORY=.next-review pnpm build`.
  The production build includes the TypeScript check.
- Browser: the existing production-build fixture review, covering 17 routes at
  1440/390/320 pixels in both themes, plus explicit HA sync and timeline failure
  inspection. Expanded timeline readability is checked in German and English at
  320 pixels. Provider probes are isolated from the owner's real services.
- Formatting: IntelliJ formatting applied to new Kotlin modules/tests. Existing
  files retain focused edits; `git diff --check` is clean. No standalone Core
  formatter/linter task is configured; Kotlin compilation and tests were run.
- Artifact checks: all nine moved files have matching SHA-256 preservation entries;
  ignored model/output/private paths do not create new tracked secrets. Git history
  was not rewritten.

Browser evidence is local under `.run/release-review/browser/`. Full and quick
results are separate. Screenshots with the `consolidation-` prefix document the
new surfaces. These are fixture browser results, not physical device evidence.

## Repository artifact classification

| Classification | Files / decision |
| --- | --- |
| active product code | Core/Web/Gateway/AI/Voice source and the 23 existing registered Voice response WAVs retained |
| active development tooling | Existing run/start/registration scripts and Web browser-review tooling retained |
| preserved experiment/evidence | Existing provider benchmark scripts, corpora, reports and 380 historical non-product WAVs retained at their documented paths |
| generated/private artifact | Runtime device/configuration snapshots, chat traces, one private replay WAV and deployment archives preserved under ignored `.run/private-evidence/` |
| obsolete/accidental artifact | Empty `=0.116,` deleted; root `.t` removed from the regular tree but preserved locally as an archive |

The `.t` archive and `.run/spotify-platform-source.tar` had the same SHA-256 and
contained 465 source/build/log archive entries. Both are preserved locally; no
historical evidence was silently destroyed. Exact moved paths and hashes are in
the [preservation manifest](2026-09-06-preserved-artifacts.md).

`.gitignore` now excludes future local audio/benchmark outputs, private replay
data, model weights, checkpoints, recordings and browser artifacts. Existing
curated benchmark evidence remains tracked intentionally. Scripts were not moved
because the historical reports reference their current paths. Build and IDE
artifacts already had ignore rules; no blind recursive cleanup was performed.

## Updated documentation and files

Documentation: root README; status README/TODO/CHAT-CONTEXT; roadmap; architecture;
Shelly integration; new HA import, platform diagnostics, ADR 0018, this report and
the artifact manifest; browser-review instructions.

Implementation: Core HA client/reconciler/persistence/controller; database
diagnostic endpoint; device catalog/commands; nullable room assignment; connection
view redaction; action/audit/gateway correlation and Voice rejection logging;
Flyway V25/V26. Web adds the HA sync route, typed diagnostics, Device/Add Device
labels and Action Inspector on the existing Activity page, with German/English
resources and focused styles. Optional HA environment entries are documented and
forwarded by platform Compose. Tests cover the corresponding boundaries.

## Open limitations, physical verification and technical debt

- **Implemented, awaiting physical verification:** real HA template execution,
  token access, registry/area mapping and Shelly values; rename/repeated sync;
  device offline/recovery; generic Nanoleaf colour and gateway timeout/offline paths.
- The initial HA setup is operator-configured, single-installation and private
  IPv4 only. It has no background sync, UI credential editor or credential rotation
  flow. Changing configuration requires a Core restart. Sync deliberately replaces
  imported names/room assignments; local deletion can be undone by the next import.
- Health is request/heartbeat/snapshot based, not an uptime history or out-of-band
  monitor. Core authentication failure limits the protected status surface. Voice
  readiness is not microphone/playback acceptance. Restart/update requirements are
  omitted because there is no reliable signal for them.
- Old actions, direct provider calls and pre-execution rejections can lack a start boundary, target name
  or fine-grained adapter reason. Generic `EXECUTION_FAILED` remains generic.
  An asynchronous command with no terminal gateway report remains incomplete;
  the inspector does not invent its result. Audit persistence failure after a
  confirmed command can leave an incomplete recording, never a fabricated success
  event or a second execution.
- Existing provider-specific control dialogs, direct experimental Shelly code,
  broad future permission profiles, restore orchestration and historical benchmark
  directories remain intentional debt. This slice does not claim to finish those
  wider productisation projects.

## Velora handoff

Review the green software checks and perform the short real HA/Shelly import smoke
test as the platform acceptance step. Then start the dedicated Velora phase from
the existing Voice path: capture/VAD, processing audio, Core action execution,
adapter result and final response playback. Use the correlation inspector to
separate execution failures from acoustic/latency problems. Record twenty physical
attempts, including offline, ambiguity, timeout and stale session cases, before
changing TTS choices. Preserve existing reviewed audio and do not reopen provider
discovery or unrelated integrations without a separate task.

The consolidation scope ends here.

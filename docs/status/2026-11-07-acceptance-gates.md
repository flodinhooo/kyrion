# KY-002–KY-005 software verification and operational gates

This evidence supplements the existing [backlog](TODO.md); it is not another
task list. Work starts on `master` at `fb3f87c`, preserving the installed Pi Web
`871c46a` / `aaUX9C2_I6tMOcrV1sImr`. KY-001 is unchanged and awaits the actual
two-user acceptance. No personal binding/account/provider approval is inferred.

## KY-002 — legacy button review

Read-only transactions on both actual databases confirm three legacy rows each,
all without grants. They refer to the same SONOFF button and room-toggle actions.
The Pi has a fresh intended-node heartbeat; Windows has only an August source
observation. Owner eligibility includes devices:read/update/execute, but that is
not consent to any binding. Device/room names, addresses and row identifiers stay
in the private six-row review sheet:
`.run/private-evidence/ky002-005/legacy-binding-review.md`.

The current UI omitted grant state and could present inactive legacy settings as
ordinary assignments. Source now displays localized unreviewed/authorized status
and explains that saving replaces **all** selected grants. Grant metadata is
validated; absent legacy metadata remains unreviewed. Duplicate gestures and
malformed grant metadata are rejected. This UI change is **not deployed**.

Existing actual-Core/PostgreSQL integration covers authenticated saving, fresh
grants, identical-resave revocation, author permission revocation, room/source/
target isolation, terminal denial and no stale replay. A new regression also
removes bindings through the authenticated API and denies their pending command.
The synthetic gateway records dispatch/results; no physical adapter is contacted.
Targeted results: GatewayAuthorityIntegrationTest29 and ZigbeeButtonBindingTest3,
zero failures/errors/skips; Web contract tests6, ESLint, typecheck and isolated production build pass.

For actual review, use the intended installation's eligible human session at
Devices → button → Button bindings. Confirm each exact gesture, current room
power targets and toggle action. Remove any unapproved row before saving: one
save replaces the whole button configuration. Never infer approval from the
private inventory or resave Windows against its stale source. Inspect actor/grant
audit, then observe physical single/double/long, offline and revoked cases in an
agreed slot. No actual binding was changed; **KY-002 remains open**.

If the owner selects installation of the source-only review UI, prepare a new
ARM64 Web artifact from the reviewed source (017dd52), retain the currently active
871c46a image/build and root-protected Compose settings, compare effective config
and change only web.image. Use a newly reviewed scoped Web activation and normal
TLS/DE/EN checks; roll back to the retained871c46a image on failure. No schema/Core
change is needed. **Do not rerun the old871c46a activation command.** Missing
decision: whether/when to install this later UI revision. This is independent of
each human's exact binding approval and never supplies that approval itself.

## KY-003 — optional central identity

Actual Pi Keycloak26.8.2 remains loopback18889/18890 with the fixed HTTPS issuer;
discovery succeeds and restricted admin/master/management paths return404.
Read-only provider SQL confirms registration disabled, email verification on,
website client disabled and zero SMTP configuration rows. Both personal Cores
return central-enabled=false. No personal account/link/role was changed.

Fresh public DNS queries fail SERVFAIL with `DNSKEY Missing / no SEP matching the
DS`. Parent DS tag167/algorithm13/digest2 validates; child signing keys do not
match that trust chain. Checking-disabled diagnostic queries expose Infomaniak
NS and auth A NXDOMAIN; they are not a proposed DNSSEC bypass. Public website
account/TLS acceptance is blocked at DNS, not established by loopback health.
The [existing pilot plan](../../infrastructure/identity/PILOT.md#read-only-recheck-2026-11-07)
now records gates, target, scope, missing decisions and rollback boundaries.
No DNS, ingress, provider settings or public registration changes were made.

Actual isolated Keycloak26.7.5/Core/Web/Website/three PostgreSQL/Mailpit acceptance
passes: synthetic registration/mail verification, website login/logout, local
owner/member enrollment, unknown central subject denied without new membership,
explicit password/confirmation-based link, central login with unchanged member
rights, real token expiry, test-provider outage, preserved local password login
and offline unlink. Mail is caught locally; no productive email/provider is used.
UnifiedIdentityIntegrationTest13, CentralIdentityProviderTest9 and
IdentityTransportTest2 pass with no failures/errors/skips. Domain tests use a
mocked provider; the full browser scenario uses actual local Keycloak transport.

First browser attempt failed before registration because the disposable provider
was still bootstrapping. The runner now waits for the exact isolated discovery
issuer (bounded120s) before starting Core; its startup budget includes that wait.
It also explicitly suppresses the personal infrastructure/.env import. The final
complete scenario passes (1.8m); Node syntax, focused ESLint/Prettier pass. The
reviewed unchanged Core JAR was reused; no unrelated full suite/build repeated.
Acceptance services were stopped afterwards; only their synthetic tmpfs data was
discarded. **KY-003 remains open** for productive domain/mail/admin/website and
real-account acceptance. Logs are private under `.run/private-evidence/ky002-005/`.

## KY-004 — voice lifecycle and timing

Read-only inventory confirms the Pi Satellite unit active since Nov6, using the
same configuration hash and installed no-speech client/dialogue hashes as the
prior accepted rollout. Batch defaults, Chatterbox selection and speaker/model/
VAD settings were not changed. Its intended Core is Windows, not the Pi Core.
The accessible user journal supplied no usable turn timing entries; no personal
transcript/audio was inspected or recorded.

Two new regressions fail on the old source: a close transport failure leaves the
dialogue in CLOSING, and each audio section logs a misleading first-chunk event.
Source now always returns the state to IDLE while preserving the close error
(no automatic replay), and marks only the first received chunk as first. Tests
also open a subsequent synthetic session and retain chunk playback order.
These fixes are **not installed**. Targeted Satellite43, Core no-speech2,
end-intent22 and playback-acknowledgement2 pass; Ruff lint/format pass. Tests mock
capture/playback/transport and never open a microphone or speaker.

Three actual Pi→configured Windows Core health round trips using the installed
bounded Satellite transport measured23.57/19.54/17.23ms (monotonic request start
through complete health-body receipt). They are transport/health timings, not
STT/model/TTS or acoustic latency. A default urllib diagnostic took approximately
18s per request due to address fallback; the installed bounded transport does
not exhibit that delay. No network/firewall change is indicated by that probe.

Reanalysis of the retained Oct31 synthetic turn, not a new dialogue: Core-local
STT916ms, model dispatch→first delta1619ms, TTS sections7764/8015ms; Pi-local
fixture start→answer receipt11977ms, player completion26248ms, inter-section
digital gap2901ms. Core and Pi clocks are not subtracted across hosts. The
receipt/player boundaries do not prove acoustic onset, output completeness or
human intelligibility; no fresh physical latency claim is made.

The [existing hearing procedure](../pi-core-and-voice-acceptance.md#current-owner-hearing-check-2026-11-07)
now gives fixed DE/EN prompts, silence/explicit-end/next-wake and complete-item/
ending/gap criteria. Physical listening and the separately approved twenty-action
matrix remain required. No models were loaded/downloaded, cloud called, speech
unit restarted or speaker output triggered. **KY-004 remains open**.

For a separately selected source-fix rollout, use a quiet slot: record the running
Satellite unit, config hash and installed dialogue module path/hash via its own
venv; compare that module to the tested baseline before changing it. Back up the
original module with its ownership/mode in protected Pi storage, stop only the
Satellite user unit, install the tested dialogue.py from1ff39bf preserving mode,
then restart only that unit. Keep Core/AI/WSL, credential/configuration, model,
reference and audio routing untouched. Verify unit health and config hash before
the owner-controlled hearing check. On failure restore the exact saved module
and that unit only. If installed source differs from the reviewed baseline, stop
for a bounded compatibility review rather than upgrading the whole environment.
Missing decision: installation of this source-only fix and a consented quiet
restart/hearing window. No deployment or automatic audio test happened here.

## KY-005 — restore isolation and host recovery

The original PostgreSQL verifier defaulted to the personal container and created
scratch databases in that cluster. It now requires an explicit disposable target,
checks its marker, network-none/no published ports/tmpfs-only storage/running
state before mutation and pins the inspected container ID against name reuse.
`-ReadOnlyManifest` preserves existing backup metadata. Fake-Docker guard tests
exercise missing manifests and unsafe target variants. An empty-Mounts case
exposed and corrected a PowerShell null-pipeline false rejection; final guard
tests3 and actual synthetic/real dump restores pass. No application was started
against either restored personal database.

Windows: the protected Nov6 dump checksum and both original cryptographic key
files match their manifests/current originals; protected config/Knowledge paths
exist. Restore in a fresh network-none tmpfs PostgreSQL passes. The separately
compiled read-only domain verifier, without Spring/workers, validates two audit
chains/8937 sealed events/874 legacy events, five encrypted credentials and eleven
secret-less references with the original backup keys. No key content is printed
or exported. Existing original backup manifest bytes remain unchanged.

Pi: final-v41 dump checksum matches; protected platform/TLS, keys/Knowledge,
Gateway and radio archives are readable without symlinks. Archived credential/
audit keys match the live keys by hash. A new network-none tmpfs restore passes
schema41; the read-only domain verifier validates four audit chains/871 sealed
events/874 legacy events, three encrypted credentials and six secret-less references
using archived original keys. No application starts in the restored namespace.
These are **same-host** drills of **pre-V46** snapshots. Neither includes subsequent
application writes. Actual Knowledge backups contain zero documents; a nonempty
synthetic original passes the file verifier and same-size corruption fails. That
minimal verifier fixture is not an ingestion/RAG or full Knowledge restore claim.

Current Windows seven-service health and guarded `Start-CoreLan -ValidateOnly`
pass: exact reviewed JAR,46 matching migrations, no pending versions or active
Calendar leases, existing restrictive guards. Helper key/directory ACLs are
protected and an owned synthetic ACL command passes; no helper currently listens
on17654. The historical live helper-start/child-lifecycle gate remains untested,
not silently fixed by healthy application services. Docker Desktop/Ollama have
user startup entries; no matching Kyrion Core/Web scheduled task was found.
Pi Docker is enabled, platform restart policies are unless-stopped, user lingering
and Gateway/Voice/media units are enabled; this does not prove full host recovery.

Selected recovery policy/client/readiness/runtime Node tests30 and Python runtime/
schema-tool tests21 pass. Actual synthetic schema/dump/restore rehearsals7 pass as
part of the63-test run described below. Satellite wheel/sdist build also passes
in an isolated build environment; the live Python environments are unchanged.
The [existing backup guide](../postgres-backup-and-restore.md) gives the new safe
invocation. The [host/off-host plan](../host-recovery-acceptance.md) specifies
preflight, outage scope, supervised Windows startup, Pi ordering limits, access
fallback and preservation of later revocations. Missing decisions: first host/
maintenance window/local-console operator and a real separate recovery destination
with encryption/key custody. No reboot, network-loss test, productive restore or
new personal backup/quiescence was performed. **KY-005 remains open**.

## Test isolation deviation and final verification

Initial native Testcontainers runs automatically started Ryuk with a Docker
socket mount, contrary to the owner's no-socket-mount boundary. This was detected
by container inspection; the owned reaper had already exited/cleaned up when the
stop was issued. It was not used to perform an administrative bypass or rerun the
previously rejected socket test. This procedural deviation is recorded explicitly.

The affected targeted suites were repeated with
`TESTCONTAINERS_RYUK_DISABLED=true`: Gateway29, binding3, identity13/provider9/
transport2 and schema rehearsals7 = **63 passing**, no failures/errors/skips.
Container inspection during/after the rerun found no socket mounts. Only owned
temporary resources were cleaned; personal containers were retained. Disabling
the resource reaper did not disable assertions, tests or bootstrap permissions.
Voice Core26 and Satellite43, Web6, real identity browser1, recovery Node30,
Python21 and restore guards3 are separate checks, not a new full-CI claim.

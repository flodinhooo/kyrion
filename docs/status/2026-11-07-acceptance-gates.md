# KY-002–KY-005 software verification and operational gates

Historical evidence from 2026-11-07. For later public website/identity
observations and current website acceptance gates, use the
[2026-11-12 website acceptance](2026-11-12-website-acceptance.md) and the
[active backlog](TODO.md). This report's early loopback, disabled-website, SMTP
and DNS observations are not current global status.

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

## Publication and prepared activation, 2026-11-07

Remote `main` initially pointed to `871c46a` on `master`. Clean local `master`
also contained an additional identity-tunnel commit `041fb1e`, outside this
publication scope. Normal explicit-ref push published only `fb3f87c`, `017dd52`,
`9719c0f`, `1ff39bf`, `cd3e5d1`, `f345027`, `90125b9`. They respectively preserve
the installed KY-001 evidence, implement KY-002/003/004/005 source work, repair
documentation encoding and scope deferred activation. No tag, release, force
push or identity-tunnel publication was performed.

[Actual CI run 42390396304](https://github.com/flodinhooo/kyrion/actions/runs/42390396304)
completed successfully: Core, Web, Website, all three Python components and
Installer. [Vercel](https://vercel.com/florianrogenmosers-projects/kyrion-website/CdukSfXXDZB7NvtQ2TfxpHNZ77tn)
reported success for `90125b9`. This does not install local Web or Satellite.
Local Gradle now disables Ryuk/reuse outside GitHub Actions; the existing
[development entry point](../development-startup.md#local-core-tests-without-docker-socket-mounts)
documents direct IDE configuration and exact-resource cleanup. The targeted
GatewayAuthorityIntegrationTest rerun passed all 29 tests without failures/skips;
the binding unit suite passed all three tests. A single-case live mount probe
with the Ryuk variable absent in the parent shell observed the disposable
PostgreSQL container with no bind mounts or socket; JUnit owns its lifecycle.
Hosted CI configuration is unchanged.

### Pi artifact inventory and activation boundaries

Read-only recheck found active Web build `aaUX9C2_I6tMOcrV1sImr`, image
`sha256:9f1a00ed82b3fef847f32a121a793b8cff76aeddbb4b8080bebf66da241ca3e8`.
Satellite still runs the Nov6 unit and original dialogue module SHA-256
`b30367c3eb1ab9e92f0ddbc5b370e9237307ff214ddcce30a2b97800c75b72a1`.
Its configuration hash remains
`22cbb2b653d5a8e7017bb7d15b51c5d9f71feccb09cff74dcc9cff94e3e0ed92`.
No audio/capture, service restart or activation occurred.

Prepared on Pi in
`/home/flodinho/.local/state/kyrion/activation-90125b9-20261107/`:

| Artifact | SHA-256 / identity |
| --- | --- |
| `web-arm64-90125b9.tar` | `5f191f1db4555e234fe63e796b7797365e7957355aa18007848d864454e23779` |
| Web image `kyrion/web:ky002-90125b9-20261107` | `sha256:bf79063124a2354e1ecabebb00221055f8058a4889e614b1298b064af6db5882` |
| Candidate Web build | `N6PUtpaaokUmjYzUdfjFf` |
| `satellite-dialogue-1ff39bf.py` | `a2c1313165c444ed5433950588c893306cb376155c533403076b18db114a25ce` |
| `rollback-web-871c46a.tar` | `643250dba69259a57ad4226ad54f50d98016e840792cee0ec08ecd7a25b421e4` |
| `source.tar` (published `90125b9`, Web and Satellite only) | `c36f088560636d2dda8dfa0ec69b5015158af5ab7e6341d85d502c5167b9742d` |

`manifest.json` records these identities. Staging is owner-only (0700); it also
contains `ACTIVATION.md`, passing `candidate-browser.json`, the exact original
`rollback-satellite-dialogue.py` and `satellite-original-metadata.json`. ARM64 Web used frozen dependencies and
the previous pinned Node base digest. Build succeeded; isolated network-none,
read-only image inspection confirmed its build ID. Satellite syntax was checked
using the installed venv; the installed module still matches the baseline.
Four candidate-image anonymous DE/EN desktop/mobile browser checks passed
against a synthetic Core on an internal network, accessed only by SSH forwarding;
owned test containers/network were removed. Root-only effective Compose comparison
remains a pre-activation check: noninteractive `sudo` requires a password. Do not send that password to an agent or reuse the previous
activation command. These artifacts contain source/runtime, no personal backups.

For Web, in a separately authorized operator slot, verify manifest/image IDs,
run isolated anonymous DE/EN desktop/mobile browser checks, compare root-protected
effective Compose to the current running service using the reviewed no-deps hash
normalization, and preserve root-only original Compose/environment. The candidate
must differ only in `web.image`. Recreate only Web with no dependencies, build or
pull; expect a brief login/page interruption (allow two minutes for health).
Check candidate build, normal TLS, assets, DE/EN, Core/schema46 and unchanged
other containers. On failure restore that slot's exact original Compose and
retained image, recreate only Web and verify old build
`aaUX9C2_I6tMOcrV1sImr`. Do not restore SQL. The new Web alone exposes localized
binding grant/review state, all-selected-grants save guidance and stricter grant/
duplicate-gesture response validation. It never authorizes a binding by deployment.

For Satellite, use the existing module-only plan above with the exact staged
`satellite-dialogue-1ff39bf.py`. Before the approved quiet slot, recheck installed
module/config hashes, preserve the exact original module with mode/owner in
protected storage, and record unit state. Stop only
`kyrion-voice-satellite.service`, replace its installed `dialogue.py` preserving
metadata, then start that unit. Expect voice unavailability for the stop/start
interval; allow two minutes to inspect unit health, without automatic audio.
On failure restore the saved module and restart only that unit. Keep the intended
Windows Core destination and all audio/model settings. Only this activation makes
close-error recovery to IDLE and one-first-chunk-per-turn logging effective.
The existing short owner hearing guide remains unchanged and is still required.

### Operational recheck

Pi and Windows still have three unapproved bindings each. Private current
inventories are in `.run/private-evidence/publication-20261107/`; exact source,
gesture, named room/power targets and action were supplied privately to the
owner for confirmation. The intended Pi source heartbeat is fresh. Room
membership is dynamic; review current `power.set` targets again before human
save. No resave or grant activation occurred. Windows still reports the intended
node last seen `2026-08-28T18:03:36.842583Z`; that stale imported observation is
not current Windows device availability and must be resolved independently.

The DNSSEC observation earlier in this report is historical. Separate identity
work has changed the pilot since that observation; no current DNSSEC assertion
or productive DNS/Keycloak/SMTP/database change is made here. Existing website
development configuration and acceptance checks already exist. Prepared missing
production placeholders are `apps/website/account.production.env.example`
(accounts disabled, exact HTTPS issuer/callback origin, separate TLS database)
and `infrastructure/identity/smtp.example.json` (partial settings, STARTTLS587,
private-password placeholder). Neither was applied. Mail delivery/recovery,
administration/MFA, separate website DB and off-device provider recovery remain
operational gates; synthetic account tests do not close them.

Recovery inventory still contains Pi `final-v41.dump` and Windows Nov6
`203846Z.dump` with manifest `sourceSchema:39` / `verifiedTargetSchema:46`.
Neither is a current V46 source dump. Original keys/config archives exist, but
must be refreshed into a consistent new set including the current Web rollback
and separately changed identity deployment. The [host recovery plan](../host-recovery-acceptance.md)
records exact missing components and preparation sequence. No personal backup
was created/exported, no host reboot or productive restore occurred. KY-001
through KY-005 remain open for their actual human/operational acceptance.

## Post-activation background follow-up

The owner completed the scoped Pi Web activation. Read-only follow-up confirms
build `N6PUtpaaokUmjYzUdfjFf`, image
`sha256:bf79063124a2354e1ecabebb00221055f8058a4889e614b1298b064af6db5882`,
healthy Web and Core UP. The [existing activation report](2026-11-07-pi-web-conflictfix-rollout.md#subsequent-ky-002-web-activation-and-read-only-confirmation)
now records the successor artifact. This supersedes earlier source-only/prepared
Web statements in this report. No activation, rollback or restart was repeated.
Pi staging `ACTIVATION.md` and `FINAL-CHECK.json` now record completed activation;
previous `FINAL-CHECK.json` bytes are retained. Original artifact manifests remain
unchanged. Root-only operator receipts are owner-confirmed, not independently
reread through the agent's unavailable noninteractive sudo access.

The owner explicitly confirmed all three Pi button mappings. Read-only inventory
matches the reviewed source UUID/IEEE, room UUIDs and toggle actions, with a fresh
intended-node heartbeat. Complete room inventories still contain only the named
power targets plus the known non-power sensor/button. However all three bindings
still have null grant/actor/source fields. No eligible authenticated application
session is available: anonymous same-origin `/api/auth/me` returns 401. No save
was attempted, no SQL grant/session was created and no device was operated.
The eligible human must log in and save the confirmed selections through Devices
> button > Button bindings after a current target check. Human confirmation,
persisted grants and physical acceptance are separate; KY-002 remains open.
Windows was not accessed or changed by this follow-up.

### Additional local Pi V46 snapshot

A new owner-only local set was created without stopping services:

- Database: `/home/flodinho/.local/state/kyrion/database-backups-v46-20261107T175611Z/core-v46.dump`.
- Matching captured runtime material: `/home/flodinho/.local/state/kyrion/recovery-material-v46-20261107T175611Z/`.
- Separate original keys and private effective runtime configuration:
  `/home/flodinho/.local/share/kyrion/recovery-secrets/20261107T175611Z/`.

Directories are `0700`, files `0600`; no prior snapshot was overwritten. Dump: 557580
bytes, SHA-256 `41fe9e1a64c2bc3d19dd8b89ef84ba4776ee4ec46f36228112c2d62e3660c9c3`.
`manifest.json` records checksums, exact source image/container/build identities,
consistency limits and the proof. Installed Core/Web/PostgreSQL images, original
Core JAR/parser and an observed Knowledge archive were retained locally. Archive
config digests match the inspected source image IDs. Captured keys match live
keys before/after proof; secret bytes never left the Pi or entered output/Git.

The dump uses pg_dump's online transaction-consistent database snapshot. It was
restored into a newly named, marked, network-none/tmpfs PostgreSQL using the
same installed PostgreSQL image:46 successful migrations, zero failed migrations.
The existing standalone read-only verifier used the exact matching reviewed Core
runtime and original keys, without Spring, application workers, devices or
providers: four audit chains, 872 sealed events, 874 legacy events, three encrypted
credentials, six secret-less references, valid=true. Actual Knowledge documents
and observed original files were both zero; this is not nonempty Knowledge
recovery evidence. Only exact IDs of owned proof containers were removed.

The initial isolated restore attempt failed before domain verification, without
retained stderr. A focused diagnostic restored the **same unchanged dump** with
identical parameters successfully. The final proof also succeeded after waiting
for final PostgreSQL PID1/readiness, with protected local logs. Initial failure
cause is not conclusively established; no test/assertion or protection was
weakened. The dump and previously exported material were not recreated to pass.

This is still same-host local backup evidence, **not a complete recovery set**.
No global application/DB/files quiescence was imposed; zero Knowledge rows/files
were observed but future concurrent uploads would require a controlled consistent
capture. Filesystem encryption is unverified. Current root-only installed
Compose/environment/TLS could not be copied through noninteractive sudo;
protected effective container configuration is not a replacement for those files.
Identity/provider backup is intentionally excluded here. Off-host transfer,
decryption/retrieval, full-host restart, application restore and reconciliation
of later grants/revocations remain open. No personal backup was transferred off
Pi, no productive database restore or hardware/audio action occurred. KY-005
and all actual user/hardware/recovery acceptance gates remain open.

## KY-005 recovery completion preparation

Preserved `dbdc8de` and the already passed 175611Z V46 dump checksum, isolated
restore and original-key audit/credential evidence. None of those checks was
repeated. Additional local-only protected captures now contain the current
Caddyfile, explicit TLS certificate/private key and the missing Caddy image,
plus the existing compiled read-only verifier and source. They were read through
already present read-only Caddy mounts, without changing permissions/mounts or
adding a privileged container. New certificate/key public components match;
the certificate matches the previously retained TLS pin. New Caddy archive image
identity matches the running image. No secret content was printed or sent off Pi.

Fresh source records/metadata are below the existing 175611Z secrets/material
roots in `additions-20261107T193554Z-d8d1ddc2/`; earlier files/manifests remain
unchanged. The two missing current host files are exactly
`/etc/kyrion/platform/compose.yml` and `/etc/kyrion/platform/platform.env`.
Noninteractive sudo requires a password. The staged capture helper prepares a
new root-only five-file/TLS-tree snapshot under `/var/backups/kyrion/local-v46-additions/`;
it never applies settings. Three new synthetic guard cases pass: additive private
copies, redirected-source refusal, and retained incomplete capture on drift.

Available GnuPG 2.4.7/libgcrypt 1.11.0 completed a synthetic AES256 tar roundtrip,
wrong-passphrase rejection and modified-ciphertext rejection. Only temporary
synthetic material/key and its own agent were used/removed. No personal recovery
passphrase/recipient/custody was chosen or created, and no personal set encrypted.
The existing [host/off-host recovery plan](../host-recovery-acceptance.md#prepared-completion-of-the-local-v46-set)
now contains the exact interactive root capture command, conditional encryption
pipeline, approved-target requirements, quarantine/isolated verification steps
and independently retrievable decryption-key requirement. No external destination
or personal transfer was selected. Current payload is about 914 MiB; target budget
is at least 10 GiB free disk/2 GiB available RAM with growth recomputed before use.

Knowledge upload-before-row publication, ingestion/reindex/audit, tombstone/file
cleanup and orphan/temp sweep require coordination. Only Core currently mounts
the document root. Read-only live observation found zero documents/jobs/tombstones,
active Calendar leases/actions/nonterminal Gateway commands/Pi voice sessions and
other active DB clients; this does not prove absence of an in-flight HTTP upload.
Packaged defaults show graceful shutdown, 30s per lifecycle phase and no relevant
environment override. A future operator-controlled Core-only drain/stop/copy/start
window is prepared, reserving 5 minutes for the current tiny DB/empty file tree.
Heavy export/encryption/verification stay outside the outage. This procedure was
not executed: Web/Core/Satellite and other production services were not restarted;
no bindings, Identity or DNS were changed. KY-005 remains open for root capture,
coordinated snapshot, personal key/custody, independent-target proof and actual
host/user/hardware recovery acceptance.

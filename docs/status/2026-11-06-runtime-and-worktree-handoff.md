# Runtime and worktree handoff

Date: 2026-11-06. Primary checkout: `fix/spaces-hardening`, `0eb44f6`.
This record separates live observations from historical software verification.

## Source and runtime inventory

| Worktree                         | HEAD      | Relationship to primary HEAD                      | Current work                                                                  |
|----------------------------------|-----------|---------------------------------------------------|-------------------------------------------------------------------------------|
| Primary / `fix/spaces-hardening` | `0eb44f6` | Current integrated source                         | Spaces hardening and Pi deployment fixes                                      |
| `calendar-ha-recovery`           | `547f0ae` | 94 commits behind; no exclusive committed changes | Dirty historical recovery implementation; preserve and compare before cleanup |
| `core-v39-compat`                | `f07c20a` | 13 primary-only / 5 compatibility-only commits    | Deliberate V39 runtime compatibility branch, not a normal merge candidate     |
| `k-data-m01`                     | `25b6fee` | Ancestor, 36 commits behind                       | Personal Knowledge implementation already integrated                          |
| `kyrion-spaces`                  | `024e1e6` | Ancestor, 56 commits behind                       | Spaces implementation already integrated; newer hardening is in primary       |

Only Calendar/HA and primary have uncommitted work. Primary already contained
Core Docker CRLF normalization, a database-password secret-file loader fix and
its tests, plus the November 2 operational report. These were preserved.
Calendar/HA contains a modified V31 and untracked V32/V33 migrations: do not
copy them over installed canonical history or blindly merge its working tree.
Comparing its 62 modified/untracked files against primary found 45 byte-identical
files, 17 differing files and zero paths absent from primary. A difference is
not proof that the old worktree contains a missing feature.
Ahead/behind numbers compare local refs; no remote freshness is asserted.

## Pi observations and activation boundary

SSH to the configured reserved address succeeds with the existing identity and
strict `kyrion-node.local` host-key verification. Live SQL confirms schema V30.
Core and Web still run `pi-20260905t140134z`; direct Core health and Web login
return HTTP 200. Voice, Spotify receiver and media player user units are active.

The initial Caddy health failure reported `can't fork: Resource temporarily
unavailable`. A scoped restart of only `kyrion-platform-caddy-1` restored its
healthy status and HTTPS login HTTP 200 using the expected hostname with an
explicit loopback mapping. Certificate trust and client DNS were not verified.
Pi-hole, Home Assistant, Matter and OTBR were not reconfigured or restarted.
The resource exhaustion cause and recurrence remain open.

Candidate `kyrion/core:0eb44f6-deployfix` and Web `0eb44f6` already exist on ARM64.
The [November 2 record](2026-11-02-service-recovery-and-pi-update.md) documents
isolated V30-to-V41 migration and Web/Core checks. This session did not repeat
that rehearsal or activate those images. `sudo -n true` still requires a
password; the installed Compose directory is `/etc/kyrion/platform`.

Concrete activation sequence once privileged operator access is available:

1. Inspect installed protected configuration without printing credentials; pin
   current image IDs, Compose/configuration and all persistent mounts.
2. Confirm current jobs, leases and in-flight actions; establish a quiet writer
   boundary for the Pi platform only.
3. Preserve the original database, credential/audit/bootstrap keys, identity,
   configuration and persistent documents as one protected recovery set. The
   preliminary November 2 SQL dump is not a complete final recovery set.
4. Restore and verify that set in isolation with original keys and candidate
   images, including audit integrity, identities, permissions and document data.
5. Apply a reviewed override to the installed configuration, retaining existing
   TLS/radio/enrollment state and adding persistent Knowledge storage. Do not
   run the fresh installer or overwrite installed Compose wholesale.
6. Switch only the intended platform services, validate V41 migration checksums,
   HTTPS and authenticated reads, and check actual configured AI/gateway targets.
   Preserve the separate Windows V39 Voice path until its own rollout is reviewed.
7. Retain the complete V30 recovery set. An old image against the migrated
   database is not rollback; restore into a separate target and reconcile writes.

## Current work order by stream

Historical handoffs contain superseded blockers. Use the combined integration
report and subsequent Spaces/Voice/accounting records when choosing work.

| Stream                     | Next actionable TODOs                                                                                                                                                                                                                                                                                                                                                                                     | Already resolved / important boundary                                                                                                                                                                                                                            |
|----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Primary / Spaces hardening | **P0:** persist originating human principal and required capability through Gateway queue/claim/retry and revalidate at dispatch; test revoked membership and deleted/reconfigured bindings. **P0:** certify silent-provider cancellation, context changes/opt-out, session/credential revocation, caches and multi-process worker retries. **P1:** supported-host recovery and real SMTP/DNS acceptance. | Single-Space runtime guard retained; Business Voice remains blocked pending person identity.                                                                                                                                                                     |
| K-Data                     | **P1:** actual local embedding and grounded browser RAG acceptance; matching DB-plus-original-files restore; target ARM64 packaging/restart/Voice compatibility. **P2:** hostile PDF/resource limits, exact-search scale/model changes. Later: partial-answer provenance.                                                                                                                                 | `25b6fee` already integrated; combined baseline and personal source/tenant checks exist. Original V36/V37 integration collision is resolved for the canonical history; divergent installed histories remain blocked. Organization Knowledge remains unavailable. |
| V39 / K-AI / Velora        | Owner repeats two audible wake/dialogue attempts, waits 10 seconds and wakes again; verify clean no-speech closure and acoustic endings/section gaps. Diagnose privileged Gateway target/stale heartbeat; prove safe host cold start and extended uptime. Real cloud acceptance and accounting reconciliation are separate.                                                                               | No-speech fix is active in compatibility artifact `f07c20a`; Chatterbox retained after human A/B decision. No spoken barge-in or under-three-second acceptance. V40/V41 source must not silently migrate Windows V39.                                            |
| Calendar/HA recovery       | Compare dirty work against canonical integrated source, retaining unique changes. Complete browser month/week/day/DST acceptance, external-origin Google edits and large-calendar checks with disposable marked data; physical HA import/offline/reconnect checks.                                                                                                                                        | Recovery/synchronization already integrated. Google reauthorization passed October 30; the older `invalid_grant` TODO is historical and does not justify new OAuth.                                                                                              |
| Installer / operations     | Complete protected deployment recovery and clean supported ARM64/clean-room acceptance; signed immutable release and protected release workflow acceptance.                                                                                                                                                                                                                                               | Fresh installer is not an updater for this existing owner Pi.                                                                                                                                                                                                    |

Recommended order: finish runtime readiness, obtain privileged Pi access and
complete the recovery-backed Pi rollout, then address Gateway principal P0 and
stream/worker lifecycle P0 before expanding Spaces. Personal RAG and physical
Voice/Calendar acceptance can follow as separate bounded tasks.

## Verification scope

Docker Desktop initially remained in engine startup. A scoped Desktop restart
recovered the engine; existing PostgreSQL then completed crash recovery without
container recreation or data deletion. Web's initial compilation was slow but
`/login` and `/recovery` subsequently returned HTTP 200. AI and Parakeet health
passed. Ollama initially exposed an empty model catalog; restarting its identified
server with `OLLAMA_MODELS=E:\Ollama\Models` restored the three existing model
names without downloads. No model/voice selection changed.

The guarded Windows Core launcher passed all 39 migration checks, found no
pending migrations or active Calendar leases, and started immutable V39 artifact
SHA256 `D023441F034B79E0E5D8F6F40194E844DBDF0074BA259C080BB56D5C04784D5B`,
PID 12808. The actual Pi probe confirmed DNS/TCP/Core health, unauthenticated
device denial, configured Voice target and all four Gateway/user units active.
This does not establish fresh authenticated dialogue or physical audio acceptance.
The Windows database remains V39; Pi remains V30.

Final local status passed **all seven required services**: PostgreSQL, Web,
Core, AI, Ollama, Parakeet STT and Chatterbox TTS. Chatterbox completed existing
reference preparation and warmup after 642.2 seconds; no voice/runtime switch
or model download was performed. A bounded direct local Gemma generation returned
`OK`; this proves local inference separately from process health, not a complete
authenticated Web/Voice turn. The initial recovery job retained earlier DB/Core
failure results even after the independent guarded recovery; final status is a
fresh check, not a reinterpretation of that failed job.
A subsequent ordinary `dev-stack.mjs start` completed successfully with all seven
checks passing and configured Pi user services active. `git diff --check` passed.
The independent public website was also started on loopback port 3001 using its
existing branding preparation and development command.
Its root page returned HTTP 200 after initial compilation.

Git ancestry/status, live Pi SQL and HTTP probes, container/unit status and local
service startup diagnostics were performed. No source implementation was changed
by this handoff. Historical test counts in linked reports are not new test runs.

# Sprint 04: secure Core LAN preparation and Pi-hole protection

## Activation after explicit user approval

The user explicitly approved the two guards, dedicated runtime, LAN listener and
Core-only interruption. Activation succeeded on October 30 at approximately
21:30 Europe/Zurich. Sections below retain the earlier preparation evidence.

### Applied and live-verified

- Two persistent Windows Block rules are active and PrimaryStatus OK:
  `Kyrion-CoreLan-Guard-NonPi-v1` and `Kyrion-CoreLan-Guard-NonPrivate-v1`.
  Their exact scope is the dedicated Java 21 executable and inbound TCP8080.
  The first blocks all IPv4 except loopback and `.115`/`.116`, and all IPv6;
  the second blocks all sources in Public/Domain. Existing rules were untouched.
- Windows rejects IPv6 `::/0`; the equivalent `::/1` and `8000::/1` prefixes
  are used. IPv4 CIDRs are read back as dotted masks and semantically verified.
  Unit tests prove the exact complement, including all address boundaries.
- Before touching Core, a temporary nonce-only HTTP canary used this exact
  Java executable, LAN IP and TCP8080. Pi `.116` received the correct nonce;
  WSL source `172.21.146.86` timed out. Existing localhost Core stayed healthy.
  The canary was removed before the Core restart. ActiveStore rule checks and
  Block precedence prevent broader Allow rules bypassing this restriction.
- Only original Core parent PID38276 and its verified Java/console children
  were stopped. The identical JAR (SHA256
  `B592336BACFD047DEDF8536D07973626B1F7A465C64B4FF8BB0D70915EB577F9`)
  was copied to ignored activation storage and started with dedicated Java21.
  All 33 installed migrations matched, no pending migrations or sync leases.
- New Core PID at acceptance: 35108. Localhost health, actual Pi-to-Core health,
  unauthenticated device denial and all seven local readiness checks passed.
  Post-activation WSL-to-LAN access remained denied. `.115` was verified as an
  allowed rule address, not tested as a second live Pi interface/source.
- No critical acceptance failure occurred; the LAN activation was retained.
  No Pi, router, DNS, WSL, Docker or other service was restarted or configured.
  Afterward Pi-hole still served DNS, TCP/UDP53 listened, container start time
  remained `2026-10-22T12:13:08.222424382Z`. Existing Kyrion-name resolution via
  the router still worked; direct Pi-hole NXDOMAIN remained unchanged.

### Process-only configuration and future starts

The first activation briefly appended the prepared global bind override. A
subsequent startup-path review found the already running generic recovery helper
could later launch JDK22 outside the program-scoped guards. The appended entry
was immediately removed without restarting anything. Final `.env` SHA256 equals
the pre-activation backup exactly. Current LAN binding remains active through
the verified Core process environment. `Activate-CoreLan.ps1` was corrected to **never** write the global bind in future
runs.

This deliberately means a later ordinary Core restart falls back to loopback,
not an unprotected LAN listener. Persistent integration of the guarded Java
selection into the generic recovery helper is follow-up work; no other running
service/helper was restarted in this task. To review a later intentional LAN
restart, identify the then-current Core PID and run:

```powershell
& infrastructure/dev/Activate-CoreLan.ps1 -CoreProcessId <current-core-pid>
# Deliberate Core interruption, only when the existing approved scope still matches:
& infrastructure/dev/Activate-CoreLan.ps1 -CoreProcessId <current-core-pid> -Apply
& infrastructure/dev/Probe-PiCore.ps1
```

The script rechecks effective guards, existing Allow rule/private profile,
runtime checksums, leases and process identity before stopping only Core. It
uses an immutable copy of the same artifact and rolls back to the original
runtime/loopback on failed startup, Pi connectivity or local stack checks.

### Voice and remaining integration limits

- Real installed Pi client authenticated, opened a session, received a valid
  24-kHz greeting WAV and closed its own session. The unmodified hostname path
  eventually passed, but took several minutes. The router advertises two IPv6
  addresses before IPv4; these are intentionally inaccessible. A process-local
  IPv4 diagnostic override passed in approximately 2–3 seconds. Neither DNS nor
  installed client/configuration was changed. The acceptance probe now offers
  `--ipv4-diagnostic` explicitly; this is not a deployed client repair.
- A real TTS-generated synthetic `Stopp.` WAV was recognized by the existing
  STT. From Pi memory it traversed the authenticated Core turn endpoint, STT,
  deterministic stop response and TTS downlink. Valid 24-kHz reply audio returned
  to the Pi, the turn completed and Core closed the session. No microphone,
  speaker, playback acknowledgement or device execution occurred. The probe
  explicitly forbids device-execution endpoints. A second close returning404
  after Core's explicit stop closure is verified/handled, not treated as failure.
- Wake-model and configured output presence were previously checked, but this
  task does not prove real wake recall or audible playback. Use the microphone/
  speaker checklist after addressing IPv6 connection latency.
- Gateway journal reports successful heartbeats, but this Windows database has
  no fresh heartbeat. The actual target is unverified. Root-owned Gateway config
  is unreadable by the existing account and noninteractive sudo requires a
  password. No permissions were changed and no password was requested/stored.
  Do not claim this running agent is connected to the Windows Core.

Reproduce the bounded greeting diagnostic without changing Pi files:

```powershell
Get-Content infrastructure/dev/Probe-VoiceSession.py -Raw |
  ssh.exe -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=kyrion-node.local `
    -i "$env:USERPROFILE/.ssh/kyrion_node_ed25519" flodinho@192.168.1.116 `
    /home/flodinho/.local/share/kyrion/voice-satellite/venv/bin/python - --ipv4-diagnostic
```

### Regression verification after activation

- Infrastructure/demo Node suite: **34 passed**.
- Full Voice Satellite suite: **56 passed**; targeted Ruff check/format passed.
- Gateway suite: **17 passed, 1 platform-specific skip**.
- Read-only runtime migration gate: **6 passed** (checksum mismatch, missing/
  pending migration, active lease, failed migration, valid BOM/CRLF checksum).
  Final real gate still reports all 33 installed checksums matching.
- PowerShell scripts parse; fail-closed legacy Apply guard, dotted-mask comparison
  and full address-boundary coverage tested. Application Kotlin/TypeScript
  source was not changed; no new Core/Web build result is claimed here.
- Local private evidence: `.run/dev-recovery/sprint04` (sanitized rule snapshots,
  activation manifest, firewall canary checks, Voice results, DNS after-check).
  Configuration backups there contain secrets and must never be shared.

Remaining work: bounded IPv4/IPv6 fallback in installed clients (separate Pi
change approval), privileged read-only Gateway target verification, guarded
runtime selection in the regular startup helper, and physical Voice acceptance.

## Historical preparation observations (before approval)

- Windows Ethernet: `192.168.1.107`, Private profile. Pi route to Windows:
  `eth0`, source `192.168.1.116`. No IP/interface changes were made.
- Firewall enabled on all profiles, effective default inbound Block. Existing
  Kyrion rule: Private, TCP 8080, sources `.115` and `.116`, local address Any.
- **Additional Allow rule matches the actual JDK 22 Core executable**, Private,
  any port/source. The narrow Kyrion rule does not override this broader Allow.
  Consequently the old activation script is now blocked before any mutation.
- Core runs natively; repository Compose publishes PostgreSQL on loopback only.
  No Docker publishing or WSL networking change is required for this repair.
- Two status checks returned actual healthy responses for all seven local
  services. Windows listener enumeration unexpectedly omitted port 8080 while
  HTTP health succeeded. Treat that enumeration as incomplete evidence, not a
  reason to restart Core or a claim that Core is stopped. Recheck before apply.
- Pi's configured system resolver is the router (`192.168.1.1` plus IPv6).
  Its normal resolver returns `kyrion-core.home -> 192.168.1.107`; no matching
  `/etc/hosts` entry exists. Direct DNS queries to Pi-hole at both `127.0.0.1`
  and `.116` return NXDOMAIN for that name. Normal external DNS succeeds
  with two A answers. Pi-hole is running **in Docker**, not as host FTL systemd
  service; TCP/UDP 53 listen. Windows uses `.116` for DNS and reproduces the
  missing Kyrion name. Do not confuse system resolution with Pi-hole resolution.
- Existing Pi Voice, Gateway, Spotify and Media Player units report active.
  Pi-to-Core TCP still times out. Authentication/session/audio acceptance is
  therefore pending; active units are not proof of a working Voice pipeline.

No Pi-hole, router, DHCP, DNS, firewall, network-interface, Core process or
active configuration changes were made. No host/Pi/WSL/Docker restart occurred.
`dig` was unavailable on Pi; bounded Python standard-library UDP queries were
used instead without installing dependencies.

## Prepared change and explicit approval boundary

Run `infrastructure/dev/Prepare-CoreLan.ps1` for preparation only. It snapshots
`.env` bytes into an ignored UUID directory under `.run/dev-recovery/sprint04`,
verifies backup SHA256, verifies the original remained unchanged and saves a
sanitized plan. The backup contains credentials: keep it local and private,
never attach it to reports. This operation neither writes `.env` nor stops Core.

Preferred minimal candidate within the existing one-listener architecture:

1. Preserve the identical running Core JAR; do not deploy parallel AI builds.
2. Use the existing dedicated Java 21 executable under
   `.run/dev-recovery/toolchain/jdk-21.0.13.0.2+1/bin/java.exe`, matching the
   project's Java 21 toolchain. Review effective application/package/service
   firewall filters, port ranges and profiles for that exact executable before
   applying; do not assume an unmatched display name proves isolation.
3. After explicit approval, set only `KYRION_CORE_ADDRESS=0.0.0.0` and restart
   only the verified Core tree. Retain existing narrow Private/TCP8080 Pi rule;
   do not edit broad Java rules belonging to other applications. If any other
   matching Allow remains, stop and present that exact scope for review.
4. A LAN-IP-only listener would remove `127.0.0.1:8080`, used by Web, health and
   local service clients. Preserving both with this single Spring listener uses
   `0.0.0.0` plus a verified firewall boundary. A second connector or OS proxy
   adds configuration and is not necessary unless the firewall cannot isolate
   the exact executable. This candidate also avoids persisting a DHCP address.

All Core HTTP routes on that listener become reachable **from allowed peers**,
not just Voice. Existing user RBAC and gateway/satellite Bearer credential
validation remain mandatory. Public health/auth/enrollment endpoints retain
their existing semantics. No separate WebSocket port needs publishing. Plain
HTTP is not TLS encryption; this plan is limited to the trusted private Pi path.

The existing broad JDK22 rule is why activation cannot safely reuse the old
launch command. Current tests do not prove rejection from another segment;
after approval inspect the actual new listener/executable and effective rules,
then test with an available unauthorized peer. Do not claim that peer test ran.

## Rollback and acceptance after approval

### Concrete firewall guards proposed for approval

Generic application rules cannot be dismissed by display name or an empty
`Package` field alone. For a boundary independent of overlapping Allow rules,
propose two new Block guards scoped **only** to the dedicated Java 21 executable
and TCP local port 8080. Existing firewall rules remain untouched:

- Guard A, all profiles: remote IPv4 ranges `0.0.0.0-126.255.255.255`,
  `128.0.0.0-192.168.1.114`, `192.168.1.117-255.255.255.255`, plus IPv6 `::/0`.
  This leaves IPv4 loopback and the two approved Pi addresses outside that block.
- Guard B, Public/Domain profiles: all remote addresses. Private Pi traffic
  remains permitted by the existing Kyrion rule. Block precedence prevents
  broader Allow rules from overriding these guards.

Neither guard has been created. Explicit approval must include both guards,
the listener change and the Core interruption. Verify guard scope before
starting a broader listener. On rollback restore and verify the original
loopback Core first, then remove only these two guards by recorded unique names.
Do not remove or rewrite existing firewall rules. This is the hardened proposal
if generic Allow rule isolation cannot be proven; do not activate the earlier
no-firewall-change candidate merely on the strength of its narrow Allow rule.

Before applying, revalidate PID/JAR identity, installed migration checksums,
active sync leases and configuration hash. Keep original process command,
runtime path and backup locally. Stop only the newly started Core if a critical
test fails. Restore the bind entry to its original absent/loopback value,
preserving any concurrent unrelated `.env` edits; launch the identical JAR with
the original Java and explicit loopback bind. Verify localhost health. Never
restore the whole backup over concurrent edits and never reset database data.

Acceptance: localhost health; Pi health and unauthenticated denial; fresh
authenticated Gateway heartbeat; `Probe-VoiceSession.py` greeting WAV and
session cleanup; all seven readiness probes; repeat external DNS and existing
local-name queries; verify restricted network scope. A fresh Pi-hole local DNS
entry forwarding the Kyrion name may be useful, but is only a recommendation:
no DNS changes are authorized or performed. Router-based Pi resolution already
works for its configured Core hostname.

Manual Voice acceptance after these pass: say “Hey Velora”, hear the greeting,
speak a harmless request, verify transcription and audible reply, say “Stopp”,
repeat. See the existing microphone/speaker checklist. Neither microphone nor
playback was invoked during this preparation.

## Verification in this sprint

- 32 infrastructure/demo Node tests passed, including two new fail-closed LAN
  preparation/activation regressions.
- Preparation script executed successfully; backup hash matches, `.env`
  unchanged, `activated=false` in saved plan.
- PowerShell parser check passed; old Apply guard rejected execution before
  mutation, as intended.
- Two real stack status checks: seven ready services each.
- Pinned SSH, Pi route, unit states, Docker Pi-hole presence, TCP/UDP53,
  direct DNS responses tested read-only. Pi-Core probe correctly failed.
- `git diff --check` passed. No application behavior changed; previous Core/Web
  build results are not presented as newly executed Sprint 04 builds.

At this preparation checkpoint activation still required explicit approval.
That approval subsequently arrived; the activation evidence at the top of this
document supersedes this historical pending status.

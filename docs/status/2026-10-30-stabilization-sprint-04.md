# Sprint 04: secure Core LAN preparation and Pi-hole protection

## Actual observations

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

- 30 infrastructure/demo Node tests passed.
- Preparation script executed successfully; backup hash matches, `.env`
  unchanged, `activated=false` in saved plan.
- PowerShell parser check passed; old Apply guard rejected execution before
  mutation, as intended.
- Two real stack status checks: seven ready services each.
- Pinned SSH, Pi route, unit states, Docker Pi-hole presence, TCP/UDP53,
  direct DNS responses tested read-only. Pi-Core probe correctly failed.
- `git diff --check` passed. No application behavior changed; previous Core/Web
  build results are not presented as newly executed Sprint 04 builds.

Activation and short Core interruption still require the user's explicit
approval, as requested in Sprint 04. Historical auto-review rejection from
Sprint 03 is not authorization. No activation was attempted in this sprint.

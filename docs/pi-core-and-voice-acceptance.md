# Pi-to-Windows Core and Voice acceptance

> Sprint 04 supersedes the activation instructions below. Read
> [the Pi-hole protection and LAN approval plan](status/2026-10-30-stabilization-sprint-04.md).
> The old `Set-CoreLan.ps1 -Apply` path is intentionally blocked: a second,
> broader Windows Java Allow rule matches the current Core executable.

This is a local development repair, not production deployment. No new radio,
voice model, AI provider, firewall rule or public port is required.

## Identified network fault

The satellite uses `http://kyrion-core.home:8080`. The Pi resolves this to the
Windows Ethernet address, but the running native Java Core binds to loopback.
Docker publishes only PostgreSQL; changing Docker publishing/WSL NAT is not the
repair for this native JVM listener. The existing firewall rule is enabled for
Private/TCP 8080 and only the reserved Pi Ethernet/Wi-Fi addresses. The physical
Windows interface is Private. Neither DNS nor the Pi configuration needs changing.

The prepared correction is the local `KYRION_CORE_ADDRESS=0.0.0.0` override and a
restart of the identified Core Java tree using a copy of its exact existing JAR.
The default repository bind remains loopback. Router DNS handles Windows DHCP
address changes; the existing reserved Pi addresses remain the firewall boundary.
Do not bind to a hardcoded current Windows LAN address or disable the firewall.

## Review and approved application

```powershell
# Current reviewed parent PID was 38276; re-identify it if it has changed.
& infrastructure/dev/Set-CoreLan.ps1 -CoreProcessId 38276
# Only after explicit authorization of this network exposure and interruption:
& infrastructure/dev/Set-CoreLan.ps1 -CoreProcessId 38276 -Apply
& infrastructure/dev/Probe-PiCore.ps1
```

Without `-Apply`, the script only validates and displays a plan. It checks JVM
identity, its reviewed Java/Windows console children, runtime artifact path,
private network/firewall and the exact reserved Pi scope. Application preserves
unrelated `.env` bytes, rejects concurrent configuration changes, copies the
existing JAR, rechecks process creation time and waits for Core health. It changes
no firewall/Pi setting and stops no WSL, database, AI, STT or TTS process.

Revalidate all installed Flyway checksums against the selected runtime JAR and
check for active Calendar synchronization leases before applying. Never select a
newly built parallel AI artifact merely to change the listener. A changed PID,
artifact or firewall rule requires a fresh review. Failed starts leave private
logs and a launch manifest under `.run/dev-recovery/sprint03/`; do not reset data.

The automatic approval review rejected actual application in this session as a
network security-boundary change plus a forced Core restart. Explicit user
approval was requested. Until that arrives, the repair is prepared, not applied.

## Automated Voice checks after network approval

`Probe-PiCore.ps1` uses the existing pinned SSH identity. It checks DNS/TCP/Core
health, denial of unauthenticated device access, satellite configuration/model
presence and existing service states. No service credential is printed or read
for authentication by this script. It exits nonzero while Core is unreachable.

For a bounded authenticated session/greeting probe, run the prepared Python file
in the Pi's existing Voice Satellite venv through the same SSH connection:

```powershell
Get-Content infrastructure/dev/Probe-VoiceSession.py -Raw |
  ssh.exe -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=kyrion-node.local `
    -i "$env:USERPROFILE/.ssh/kyrion_node_ed25519" flodinho@kyrion-node.local `
    /home/flodinho/.local/share/kyrion/voice-satellite/venv/bin/python -
```

This uses the installed client and normal enrolled service configuration. It first
checks Core health, opens one new authenticated Voice session, requests/validates
its greeting WAV and closes only that session in `finally`. It neither opens a
microphone nor plays audio. An unreachable Core is rejected before constructing
the credential-using client. It does not inspect unrelated token caches.

The configured production path here uses HTTP/JSON with streamed voice turns.
Experimental PCM/WebSocket modes are not automatically enabled or substituted.

## Manual microphone/speaker acceptance

1. Confirm all local services and `Probe-PiCore.ps1` are healthy. Check a fresh
   Gateway heartbeat in System services, not merely `systemctl active`.
2. At the Pi, confirm the intended USB microphone and Bluetooth/PipeWire output
   are selected. Inspect the current sink/mute state with `wpctl status` and
   `wpctl get-volume @DEFAULT_AUDIO_SINK@`. Choose a comfortable volume yourself;
   no script should force it to 100%.
3. Say **Hey Velora** near the intended microphone. Confirm detection, one
   authenticated Core session and an actually audible acknowledgement.
4. Speak a harmless sentence/request. Confirm STT, a Core turn result, generated
   reply audio and audible playback from the intended speaker. Do not use a
   physical device command for the first acceptance.
5. Say **Stopp**, then repeat the wake phrase. Confirm a fresh session and normal
   listening/playback without restarting services. Record audible outcome and
   timestamps; do not put private recordings or transcripts in Git.
6. Reconnect/outage tests must be coordinated separately. Do not interrupt a
   shared WSL/Docker session or repoint the Pi to another Core to simulate failure.

Process/API success, a valid WAV and successful SSH transfer are separate from
real wake-word recall, microphone capture and audible output acceptance.

## Optional manual Google-origin edit

The previous revoked authorization was superseded by the user's successful
reauthorization; no new consent is needed while the integration reports healthy.
To verify a genuinely external edit, create a separate clearly marked
`[KYRION-MANUAL-GOOGLE-TEST]` event in Samsung/Google, select that same calendar
and date range in Kyrion and refresh. Edit only that test object's title/time in
Samsung/Google, refresh Kyrion and verify one updated event. Delete only that test
object and verify disappearance. Do not use the user's existing October 31
09:00-22:00 appointment for testing. A linked local event has its separate explicit
synchronization/conflict rules; do not enable global synchronization just to run
this read-only range-view acceptance.

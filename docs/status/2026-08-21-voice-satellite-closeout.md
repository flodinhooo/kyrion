# Voice Satellite closeout — 2026-08-21

## Outcome

The physical Voice Satellite successfully controlled the hallway and bedroom
lights with one German multi-room command after the STT replacement. The first
live attempt through NVIDIA Parakeet succeeded. This closes the day's primary
goal: make the spoken Hue path reliable enough to continue physical iteration
without further Faster-Whisper transcript patches.

## Changes completed

- Replaced numeric Core addressing in node configuration with router-provided
  local DNS (`http://kyrion-core.home:8080`). This keeps the Core contract
  stable across DHCP address changes while authentication and firewall policy
  remain mandatory.
- Confirmed that the node appears on both Ethernet and Wi-Fi; local DNS names
  the Core host, not a particular node interface.
- Added deterministic German and English multi-room light-power proposals.
  Core resolves every named room authoritatively before executing any target.
- Added hallway synonyms and bounded handling for observed German ASR wording.
- Corrected the stale Nanoleaf bedroom endpoint from `192.168.1.114` to the
  current reserved address `192.168.1.102` after verifying reachability.
- Replaced Faster-Whisper `small/int8` final transcription with the
  provider-neutral `http_openai` STT adapter and local NVIDIA Parakeet TDT 0.6B
  v3 through NeMo-Speech.cpp on port 8040.
- Preserved explicit DE/EN locale, upstream VAD, visible `STT_UNAVAILABLE`
  failure and no silent engine fallback.
- Added typed `action.processing` responses emitted only after Core validates
  an action proposal. Core checks the active session again after feedback and
  before device execution; the later response still reflects the real outcome.
- Generated two Velora takes for four German processing responses and four
  additional greetings. The owner selected one take for every line; only those
  eight WAVs were registered as checksum-pinned production assets.

## Physical evidence

- Earlier Faster-Whisper attempts frequently returned `Alles klar` without an
  action because critical command wording was transcribed incorrectly.
- The final Faster-Whisper-era multi-room attempt reached Core but only the Hue
  hallway targets succeeded; the bedroom Nanoleaf endpoint was stale.
- After endpoint correction and the STT replacement, the owner reported that
  the first Parakeet live attempt succeeded.
- The new processing feedback and expanded greetings are deployed and ready
  for the next physical command; the owner ended the session before recording
  that final listening/execution acceptance.

## Verification

- Parakeet fixed Delock set: command meaning improved over the productive
  Faster-Whisper path; warm local HTTP transcription measured 0.244 seconds.
- Known Parakeet limitation: three of six noise-only clips produced a short
  final without upstream VAD, so the Satellite VAD remains mandatory.
- AI: 106 tests passed; Ruff passed.
- Core: complete test suite passed.
- All 16 generated voice candidates passed mono PCM16/24 kHz validation and
  produced the intended Parakeet transcript.
- All four selected `action.processing` assets resolved from the running AI
  service as HTTP 200 RIFF/WAV responses.
- AI and Core health checks passed after restart. Parakeet, PostgreSQL, Ollama,
  Web, Core and AI were intentionally left running at closeout.

## Security note

Do not configure the Core host or Raspberry Pi as a router DMZ/exposed host for
future mobile control. Core device-control endpoints must not be published
directly to the internet. Use an authenticated VPN or a deliberately designed
remote-access gateway with TLS, narrow ingress, revocation and audit when
mobile access outside the LAN is implemented.

## Next Voice session

1. Run one physical Hue/Nanoleaf command and confirm the audible order:
   greeting, transcript processing response, device change, truthful result.
2. Confirm that all four processing variants can play across repeated turns
   and never appear for ordinary dialogue or rejected proposals.
3. Record at least twenty consecutive physical action attempts, including
   multi-room, off, on, unavailable-device and partial-success cases.
4. Add a typed partial-success outcome instead of mapping partial execution to
   generic failure.
5. Complete English fixed assets and DE/EN physical acceptance.

Thread/Matter work was performed concurrently in a separate chat. Its commits
and files are deliberately not evaluated or claimed as accepted by this Voice
closeout.

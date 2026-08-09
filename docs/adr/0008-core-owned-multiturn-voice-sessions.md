# ADR 0008: Core-owned authenticated multi-turn voice sessions

## Status

Accepted for the first Raspberry Pi dialogue slice on 2026-08-09.

The provider selection and batch speech pipeline in this ADR are superseded by
[ADR 0009](0009-local-provider-neutral-streaming-voice-pipeline.md). The
Core-owned identity, authorisation, session and execution boundaries remain in
force. Azure Speech and Piper below describe the initial decision only; they
are not the current target architecture.

## Context

The first Voice Satellite performs local wake-word inference but has no
post-wake dialogue path. Browser chat currently uses an owner session cookie
and Next.js orchestration. A headless satellite must not copy browser
credentials, reuse the more privileged gateway-agent credential, call the AI
service directly, or gain device-execution authority.

A useful room assistant also needs one wake word to open a bounded multi-turn
session. Requiring the wake word after every response is not an acceptable
product interaction. Ambient audio must nevertheless remain local outside an
explicit post-wake session.

## Decision

Core owns Voice Satellite identity, credentials, owner scope and dialogue
session lifecycle. A satellite receives a separate least-privilege credential
through an owner-created, one-time enrollment. The credential authorises only
the bounded voice endpoints for that satellite.

For the first co-located development installation, an already owner-enrolled
gateway may bootstrap its local Voice Satellite once. Core derives owner scope
from the authenticated gateway, issues a new voice-only credential and records
the registration. The Voice Satellite never receives or retains the gateway
credential after provisioning. Product onboarding continues to use explicit
owner enrollment.

One local wake detection opens one Core voice session. The session may contain
multiple sequential turns and retains one Core-owned conversation identifier.
It closes after an explicit stop phrase, an inactivity timeout, a configured
maximum lifetime, credential failure or an unrecoverable processing error.
Each utterance has a strict duration and byte limit.

The satellite owns local capture, wake detection, voice activity detection,
acknowledgement cues, playback and interruption detection. It sends audio only
after a local wake event and does not persist it after the bounded request has
completed. Core authenticates the satellite, resolves its owner and records
session/turn outcomes. The AI service provides replaceable local speech and
language capabilities; it does not authenticate satellites or execute device
commands.

The first local speech providers are:

- a lightweight frame-based VAD on the satellite;
- faster-whisper behind the AI service for German/English STT;
- Microsoft Azure Speech with `de-DE-KatjaNeural` as Velora's primary TTS
  voice. Text responses leave the local system for synthesis; audio capture and
  STT remain local. Credentials remain server-side and no other voice is used
  as a silent fallback.
- Piper as an explicitly selected local development provider, not the product
  voice or an automatic fallback.

Speech runtimes and voice models remain separately installed artifacts with
recorded versions, checksums and licences. Piper's engine licence and each
voice model card must be reviewed before distribution. Neither provider is a
public Kyrion contract.

The session state model is:

```text
idle -> acknowledging -> listening -> processing -> speaking
                         ^                         |
                         +------ follow-up -------+

any active state -> closing -> idle
speaking + user speech -> interrupted -> listening
```

Core-confirmed action results remain mandatory before spoken success. The
initial conversation slice may answer without device actions, but it must not
introduce a second execution path that bypasses the existing Core command
boundary.

## Consequences

- Voice and Web share Core-owned conversation history without sharing client
  credentials.
- A compromised satellite credential cannot poll gateway commands or act as a
  browser owner session.
- Multi-turn, timeout and interruption semantics are explicit from the first
  contract.
- The implementation requires a new persisted satellite credential/session
  model and bounded binary request handling in Core.
- STT and TTS availability are visible runtime dependencies. Missing Azure
  credentials or connectivity produce a typed failure rather than changing
  Velora's voice.
- Full-duplex acoustic echo handling remains a physical acceptance item. Basic
  playback cancellation can precede reliable barge-in, but the state and
  protocol must already support interruption.

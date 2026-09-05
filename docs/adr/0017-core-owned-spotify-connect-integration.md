# ADR 0017: Core-owned Spotify account and Connect integration

- Status: Accepted
- Date: 2026-09-04

## Context

Kyrion should let an owner connect a Spotify account in Web, inspect available
Spotify Connect players and select the Raspberry Pi speaker as a playback
target. Provider credentials must not enter Web, the AI service or the gateway
agent. The Raspberry Pi already owns the local PipeWire and Bluetooth playback
path used by the Voice Satellite.

Spotify's Web API requires an exactly registered HTTPS redirect URI, with an
HTTP exception for explicit loopback IP addresses. `localhost` itself is not
accepted by Spotify. Reading
Connect devices and transferring playback require the
`user-read-playback-state` and `user-modify-playback-state` scopes. Player API
control requires Spotify Premium. The proposed Raspberry Pi receiver,
`librespot`, is an unofficial open-source client rather than a Spotify SDK.

## Decision

- Kyrion Core owns Spotify OAuth, encrypted token persistence, refresh and all
  Spotify Web API calls.
- Web starts an owner-authenticated OAuth flow and receives only connection and
  device metadata. A short-lived, one-time, owner-bound state value protects
  the callback.
- The initial permission set is limited to playback-state reads and playback
  control. Library and profile-email access are not requested.
- Playback transfer is a typed Core action and produces an owner-scoped
  activity event.
- The Pi receiver is a separate least-privilege user service using the existing
  PipeWire/PulseAudio compatibility boundary. It receives neither Kyrion Core
  credentials nor Spotify Web API OAuth tokens.
- Premium requirements and the unofficial receiver boundary remain visible in
  setup documentation and UI. Kyrion must not claim official Spotify
  certification.

## Consequences

The account connection can be removed without changing the Pi receiver, and
the receiver can be replaced without changing Core contracts. Access and
refresh tokens are protected by the existing installation credential key.
OAuth state is intentionally process-local and expires after ten minutes, so a
Core restart during login requires the owner to restart the flow.

The first slice transfers existing playback only. Search, playlists, pause,
skip, volume, voice commands, ducking and automatic player lifecycle are
follow-up work through the same Core-owned policy boundary.

## Subsequent scope (2026-09-05)

The Lounge player now supports pause/resume, skip and volume. A bounded shelf
of six account playlists adds `playlist-read-private` to new authorizations;
existing grants require explicit renewal through Spotify for this capability.
Core validates playlist and device selection and audits execution. The shelf
does not claim a recently-played ordering or retain listening history.

## Local development clarification (2026-09-05)

Core permits HTTP callbacks only on `127.0.0.1` or `[::1]`; HTTPS remains
required for other hosts. Web may relay an HTTP loopback callback to the
explicitly configured `http://localhost` public origin on the same port,
before checking the existing host-only session. This preserves normal localhost
development without transferring session cookies between hosts. Only OAuth
code, state and denial parameters are relayed to the fixed callback path.
Core still validates the authenticated owner and its expiring, single-use state
and exchanges the code with the original registered redirect URI.

# Spotify Integration

## Implemented slice

Kyrion Web exposes an official internal Spotify integration page and a
[Lounge player](lounge.md). The owner can
start Spotify's Authorization Code flow, disconnect the account, load currently
available Spotify Connect devices and transfer active playback to one device.
Core requests only `user-read-playback-state` and
`user-modify-playback-state`, encrypts access and refresh tokens with the
installation credential key and records connection, disconnection and transfer
events. The Lounge adds current playback metadata, resume/pause, previous/next
and supported device volume. Tokens are never returned to Web.

Configure Core with:

```text
KYRION_SPOTIFY_CLIENT_ID=<Spotify dashboard client ID>
KYRION_SPOTIFY_CLIENT_SECRET=<Spotify dashboard client secret>
KYRION_SPOTIFY_REDIRECT_URI=https://kyrion-node.local/api/integrations/spotify/callback
```

The redirect URI must be registered exactly in the Spotify developer
dashboard. New development-mode apps support a bounded allowlist and require a
Premium owner account. Refresh tokens currently expire after Spotify's
documented six-month lifetime and then require owner reauthorization.

## Raspberry Pi player

Update, 2026-09-05: the owner reports successful physical playback by selecting
`Kyrion Pi` from Spotify on the phone. Receiver installation scripts and the
systemd service are present in the repository. The original setup checkpoint
below predates that successful validation and is retained as historical context.

The original planned player name was `Kyrion Wohnzimmer`; the owner verified
the receiver as `Kyrion Pi`. The receiver uses the existing PipeWire/PulseAudio
audio path to reach the Bluetooth speaker. `librespot` is unofficial and
Premium-only. Installing or changing the receiver remains separate from Web
account connection and playback control.

## Deliberate follow-up

- verify receiver and Bluetooth audio recovery after a reboot;
- verify that `Kyrion Pi` appears in Kyrion Web as well as in the phone app;
- pause, resume, skip and volume are now implemented as bounded Core commands
  with a Web player in [Lounge](lounge.md); live Web-to-player validation remains;
- add search and playlist selection through Core;
- coordinate music ducking with Voice Satellite responses.

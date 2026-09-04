# Spotify Integration

## Implemented slice

Kyrion Web exposes an official internal Spotify integration page. The owner can
start Spotify's Authorization Code flow, disconnect the account, load currently
available Spotify Connect devices and transfer active playback to one device.
Core requests only `user-read-playback-state` and
`user-modify-playback-state`, encrypts access and refresh tokens with the
installation credential key and records connection, disconnection and transfer
events. Tokens are never returned to Web.

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

The intended player name is `Kyrion Wohnzimmer`. A `librespot` receiver will
run as the existing interactive audio user and use PipeWire's PulseAudio
compatibility service so it can reach the Bluetooth speaker without elevated
device or Docker permissions. `librespot` is unofficial and Premium-only. It
must be version-pinned and physically verified before this part is marked
implemented.

At present the Pi has active PipeWire, PipeWire Pulse and WirePlumber user
services, but no `librespot` binary and no active audio sink. Installing the
receiver and reconnecting the speaker therefore remain explicit administrator
and physical validation steps.

## Deliberate follow-up

- install and pin a reviewed ARM64 `librespot` build;
- reconnect and persist the intended Bluetooth audio sink;
- verify that `Kyrion Wohnzimmer` appears in Spotify and in Kyrion Web;
- add pause, resume, skip, volume and search as typed Core actions;
- coordinate music ducking with Voice Satellite responses.

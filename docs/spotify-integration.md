# Spotify Integration

## Implemented slice

Kyrion Web exposes an official internal Spotify integration page and a
[Lounge player](lounge.md). The owner can
start Spotify's Authorization Code flow, disconnect the account, load currently
available Spotify Connect devices and transfer active playback to one device.
Core requests `user-read-playback-state`, `user-modify-playback-state` and
`playlist-read-private`, plus `user-read-recently-played`, encrypts access and refresh tokens with the
installation credential key and records connection, disconnection and transfer
events. The Lounge adds current playback metadata, resume/pause, previous/next
and supported device volume. It also lists up to six playlists
and starts a listed playlist on the selected Connect device. Tokens are never
returned to Web.

Existing connections keep working for playback. Choose **Renew Spotify access**
on `/plugins/spotify` to grant listening-history access. No disconnect is needed.
Core reads the latest 50 track plays, sorts by `played_at`, extracts distinct
playlist contexts and resolves metadata for the latest six. Missing contexts,
albums and invalid IDs are excluded. If playlist details return 403/404, Core
tries Spotify's public oEmbed endpoint for the same validated playlist ID.
Only title and an allowlisted cover URL are used, never returned HTML; account
tokens are not sent to oEmbed. Playlists unavailable through both are omitted; the
shelf fills remaining slots from the first 50 library playlists, deduplicated by
ID, up to six entries. Recent entries retain priority. The owner requested
multiple directly playable choices rather than a strict history-only shelf.
This is a bounded view of Spotify's available history, not a complete lifetime
playlist history. Listening history is neither persisted nor logged.
See [Spotify recently played](https://developer.spotify.com/documentation/web-api/reference/get-recently-played).

A local read-only diagnosis confirmed 50 history entries, ten playlist contexts
and one distinct playlist: the authenticated details endpoint returned 404,
while Spotify oEmbed returned 200 with title and cover. This caused the previous
empty shelf. The fallback addresses that observed response without inventing
additional recently played playlists.

The corrected client was then verified read-only against the existing account:
one playlist with a non-empty name and cover. Spotify's `pickasso.spotifycdn.com`
cover host is explicitly allowed in Core and Web; lookalike hosts remain denied.
No playback commands were issued during diagnosis. Targeted Core tests cover
404 fallback, missing previews, malformed data and propagation of rate limits.

`GET /v1/integrations/spotify/playlists` returns `reauthorizationRequired` and
at most six `items` with ID, name, safe cover URL and Spotify link.
`PUT /v1/integrations/spotify/playback/playlist` accepts `playlistId` and
`deviceId`. Core checks the owner's returned playlists and available,
unrestricted devices, then records the command result without playlist names.

## Playback refresh resilience

A successful player command and refreshing the display are separate outcomes.
Web waits briefly after a command and retries only state reads up to three
times for transient failures or an unchanged track immediately after skipping.
Commands are never automatically replayed. The last confirmed view is retained
during retry. Persistent read failures show a status-refresh message, not a
failed-command claim, and the periodic refresh can recover it automatically.
Non-server HTTP read errors do not enter the immediate retry loop.

The adapter accepts successful write responses without requiring a JSON body,
including empty HTTP 200 responses. Empty HTTP 200 state reads remain errors;
HTTP 204 represents no current playback.

In a controlled browser reproduction, an accepted NEXT followed by one failed
state read produced the old generic error and stale title. The updated path
recovered the new title automatically while sending NEXT exactly once. The
original live Spotify response status was not captured; this is reproduced
client failure handling and defensive adapter coverage, not proof of a specific
provider failure. Verified with 54 Web tests, 13 Spotify Core tests, TypeScript,
ESLint, Web/Core builds and mocked browser playlist selection/playback.

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

## Local Windows development

Register this additional redirect URI in the Spotify dashboard, keeping the
existing Pi URI:

```text
http://127.0.0.1:3000/api/integrations/spotify/callback
```

Set `KYRION_SPOTIFY_REDIRECT_URI` to that URI for the local Core process and set
`KYRION_PUBLIC_URL=http://localhost:3000` in `apps/web/.env.local`. Restart Core
after changing its environment. The Web UI can continue to use
`http://localhost:3000`, including login and Spotify connection.

Spotify requires an explicit loopback IP for HTTP redirects and rejects
`localhost`. The Web callback relays code/state or denial parameters from
loopback to the configured localhost callback on the same port before reading
the host-only session. This relay sets no cookies and uses no-store/no-referrer
headers. Core still requires the initiating owner, validates single-use state,
and exchanges the code using the original registered loopback URI. HTTP
callbacks to non-loopback hosts remain unavailable. Production HTTPS callbacks
continue through the existing path.

See [Spotify redirect requirements](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri).

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

The Web player interpolates elapsed playback time between provider snapshots
and offers a seek slider. Core validates `SEEK` commands against the active
device, track duration and Spotify's seeking restriction before calling the
provider. `positionMs` must be an integer in the current track and no greater
than 86,400,000 ms. Successful seek commands use the existing audit and status
refresh path. Restart an older running Core when installing the playlist and
seek endpoints; an existing Spotify grant may additionally require renewal for
`playlist-read-private` and `user-read-recently-played`.

- verify receiver and Bluetooth audio recovery after a reboot;
- verify that `Kyrion Pi` appears in Kyrion Web as well as in the phone app;
- pause, resume, skip and volume are now implemented as bounded Core commands
  with a Web player in [Lounge](lounge.md); live Web-to-player validation remains;
- add search and broader playlist browsing through Core;
- coordinate music ducking with Voice Satellite responses.

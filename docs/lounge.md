# Lounge

The Web route `/lounge` groups entertainment by Music, Videos and Photos.
Each tab contains a horizontally scrollable source carousel with named source
buttons, previous/next controls and selectable dots. Touch scrolling uses native
CSS scroll snapping. Source navigation never starts or interrupts playback.
The interface supports German and English and the existing light/dark themes.

## First implemented slice

Spotify account setup remains at `/plugins/spotify`, linked from the player.
An authenticated owner can view the current title, artist, cover, progress and
available Spotify Connect devices; resume/pause playback; skip backwards or
forwards; select an output device; and adjust supported device volume.
Changing output preserves the current playing/paused intent. Playback is
refreshed every 15 seconds while the browser document is visible and after
commands. Failed requests disable controls until a successful refresh.
Provider-reported action restrictions disable the corresponding controls.

Resume uses the existing Spotify playback context. Search, library browsing
and starting an arbitrary playlist entirely within Kyrion are not implemented.
The player links to Spotify for initial content selection. There is no browser
audio runtime or cross-page mini-player in this slice.

YouTube Music, YouTube, Jellyfin and NAS cards are explicitly labelled planned.
They have no connection or execution controls yet. A future NAS connection
should be shared across the Music, Videos and Photos tabs rather than set up
independently for each media type.

## Ownership and contracts

Web uses authenticated same-origin routes with CSRF validation for mutations.
Core owns Spotify credentials, provider requests, validation and audit records.
No additional OAuth scopes or dependencies are introduced.

- `GET /v1/integrations/spotify/playback`: typed playback metadata, nullable
  title/artist/artwork/link/device, progress/duration and provider restrictions.
  No current playback produces an empty state, not an error.
- `PUT /v1/integrations/spotify/playback`: `action` is one of `RESUME`, `PAUSE`,
  `NEXT`, `PREVIOUS`, `VOLUME`; `deviceId` is required; `volumePercent` is an
  integer from 0 to 100 required only for `VOLUME`.
- Existing `PUT /v1/integrations/spotify/playback/device` transfers playback.

Core checks device reachability in the account's current device list,
restrictions and volume support before new playback commands. Successful and
failed commands record an owner-scoped activity event with a correlation ID;
listening history and tokens are not included in those events. Artwork and
track links are restricted to HTTPS Spotify hosts before rendering.

The implementation follows Spotify's [playback-state API](https://developer.spotify.com/documentation/web-api/reference/get-information-about-the-users-current-playback)
and [resume API](https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback).
Provider acceptance of a command is followed by a fresh state read; it is not
proof that physical speakers emitted audio. Live hardware validation remains
separate from automated contract and service tests.

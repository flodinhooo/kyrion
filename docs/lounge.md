# Lounge

The Web route `/lounge` groups entertainment by Music, Videos and Photos.
Each tab contains a horizontally scrollable source carousel with named source
buttons, previous/next controls and selectable dots. Touch scrolling uses native
CSS scroll snapping. Source navigation never starts playback. Spotify playback
continues on its selected output; YouTube embeds stop when their card is hidden.
The interface supports German and English and the existing light/dark themes.

## First implemented slice

Spotify account setup remains at `/plugins/spotify`, linked from the player.
An authenticated owner can view the current title, artist, cover, progress and
available Spotify Connect devices; resume/pause playback; skip backwards or
forwards; select an output device; and adjust supported device volume.
Changing output preserves the current playing/paused intent. Playback is
refreshed every 15 seconds while the browser document is visible and after
commands. Transient post-command state failures are retried automatically;
status-refresh errors are distinct from command failures and retain the last
known display without locking out playback controls.
Provider-reported action restrictions disable the corresponding controls.

When Spotify has no current playback, an accepted output transfer can still
return no active device. Lounge retains that explicitly selected, Core-accepted
output while it remains in the account's device list, enabling resume or a
playlist start. This is local UI intent, not a claim of active playback. Actual
playback/active-device observations take precedence; disconnecting or losing the
device clears the selection. A failed transfer does not replace the prior choice.

Resume uses the existing Spotify playback context. A shelf lists up to six
recently played playlists and can start one on the selected device. These are
deduced from playlist contexts in the latest 50 track plays, newest first.
Listening-history access requires renewing older Spotify grants. Search and full library browsing
remain follow-up work. The player also links to Spotify for content selection. There is no browser
audio runtime or cross-page mini-player in this slice.

YouTube and YouTube Music now accept links for an official browser video player;
see [YouTube integration](youtube-integration.md) for supported links and limits.
Jellyfin and NAS cards remain explicitly labelled planned, without connection
or execution controls. A future NAS connection
should be shared across the Music, Videos and Photos tabs rather than set up
independently for each media type.

## Ownership and contracts

Web uses authenticated same-origin routes with CSRF validation for mutations.
Core owns Spotify credentials, provider requests, validation and audit records.
Playlist browsing adds the `playlist-read-private` scope; no new dependencies
are introduced.

- `GET /v1/integrations/spotify/playback`: typed playback metadata, nullable
  title/artist/artwork/link/device, progress/duration and provider restrictions.
  No current playback produces an empty state, not an error.
- `PUT /v1/integrations/spotify/playback`: `action` is one of `RESUME`, `PAUSE`,
  `NEXT`, `PREVIOUS`, `VOLUME`, `SEEK`; `deviceId` is required; `volumePercent` is an
  integer from 0 to 100 required only for `VOLUME`. `SEEK` requires an integer
  `positionMs` within the currently playing track on that device. Core rejects
  seeking when Spotify disallows it or when the target is outside the track.
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

## Verification (2026-09-05)

The Spotify timeline now advances locally between playback snapshots, stops
when paused and supports pointer/touch and keyboard seeking. It resynchronizes
with provider snapshots after commands. Playlist failures distinguish an old
Core without the endpoint from other failures; existing grants without playlist
access show the reauthorization path.

The timeline follow-up passed TypeScript, ESLint, all 59 Web tests, targeted
Spotify Core tests and both application builds. An isolated Chrome test verified
clock advancement, clicking the timeline, six playlists, playlist playback on
the selected device and recovery from a failed status read without repeating
NEXT. The local Core was restarted successfully with the new endpoints;
real-account playlist access still depends on the owner's OAuth grant.

- Web: TypeScript, ESLint, production build and 37 tests across 15 test files.
- Core: seven Spotify service/boundary tests and the executable application build.
- Headless Chrome against an isolated mock Core: desktop and 390px layouts,
  pause/resume, output transfer preserving playback intent, volume, source
  carousel, media tabs, provider errors, disconnected setup and runtime errors.
- Real phone-to-Pi audio is owner-reported; the new Web-to-Pi control path has
  not yet been physically validated or deployed as part of this change.

The subsequent YouTube slice passed four Core link/audit tests, the Web suite
(49 tests across 19 files), TypeScript, ESLint and both application builds.
Headless Chrome with a mocked Core and intercepted YouTube frame verified
explicit loading, invalid-link feedback, video/music destinations, no autoplay,
frame removal on source/tab changes, closing, and desktop/390px layouts.
This does not verify real YouTube media availability, Premium behaviour or a
deployment to the running installation.

The playlist shelf now fills unused slots with library playlists, up to six
unique choices. Recently played entries come first. Every entry uses the same
validated playback command for the selected output device.

## Live control verification (2026-10-22)

Using the account holder's normal browser login, real Core/Spotify reads found
three Connect devices including Kyrion. The browser issued PAUSE and RESUME on
the selected Kyrion output; subsequent provider state confirmed both. A one-step
volume change and restoration of the original volume were likewise accepted and
confirmed through the device list. The initial playing intent was restored.
This verifies the Web/Core/provider path, not audible speaker output.

The first idle-device check exposed a separate UI defect: Spotify accepted the
transfer but returned no track or active device, so Lounge lost the chosen output.
The player now retains a Core-accepted idle selection as described above. Three
unit regressions cover idle selection, provider-state precedence and absent
devices. An isolated browser with intercepted Spotify responses additionally
verified controls becoming enabled after an accepted idle transfer, preserving
the prior selection after rejection, clearing a disappeared device and clearing
selection across disconnect/reconnect. These fixture checks are distinct from
the real-account control verification.

All 111 Web tests, TypeScript, ESLint, production build and `git diff --check`
passed. No Core code, credentials or account authorization were changed.

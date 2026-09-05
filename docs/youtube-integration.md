# YouTube and YouTube Music in Lounge

## Implemented slice

Lounge offers YouTube under Videos and a YouTube Music link entry under Music.
The owner pastes an HTTPS video or playlist link and explicitly chooses **Load
player**. Core resolves the link locally into a typed, canonical embed response.
Only then does Web load the official YouTube privacy-enhanced iframe player.
Playback starts using the provider's own controls, without autoplay.

Supported inputs: `youtube.com`, `www.youtube.com`, `m.youtube.com`,
`music.youtube.com` watch links; `youtu.be` links; Shorts and live video links;
and playlist links. Watch links containing a playlist resolve to the selected
video only. Tracking parameters and timestamps are discarded. Playlist
availability, including private or generated mixes, is determined by YouTube.

The Music card uses the same visible YouTube video player. It is not a native
YouTube Music account integration, audio-only player or personal library.
The visible card explicitly identifies this as a link player without an account
connection and states that personal libraries and Premium accounts are not imported.
Direct links open the original YouTube or YouTube Music destination when an
embed is unavailable or the owner wants the full service experience.

## Ownership and privacy

- `POST /v1/integrations/youtube/embed` accepts `{ url, source }`, with source
  `VIDEO` or `MUSIC`; it returns `{ embedUrl, watchUrl }`.
- The same-origin Web route requires the existing owner session and CSRF token.
- Core owns host/path/identifier validation and records `YOUTUBE_EMBED_PREPARED`
  with owner and correlation ID. It does not store the link, video identifier,
  listening history or Google credentials in that event.
- Core never fetches supplied URLs. No Data API key, OAuth flow or media-stream
  extraction is introduced. Preparing an embed does not claim successful playback.
- Web validates returned destinations before rendering. The iframe uses
  `www.youtube-nocookie.com`, native controls, fullscreen and an origin-only
  cross-origin referrer so YouTube can identify the embedding site.
- Google receives browser connection data when the owner loads the player;
  this is explained beside the button with a Google privacy-policy link.
- Leaving the selected source/tab or hiding the document unmounts the iframe,
  stopping hidden playback. Returning reloads the prepared player without
  autoplay; position is not retained. Explicitly closing clears preparation.
- Source labels/icons load locally. There are no YouTube requests on initial
  Lounge load or merely selecting a YouTube card.

## Intentional limits

Playback occurs on the current browser device. The Spotify output-device list
does not apply. Raspberry Pi playback, Cast discovery/control, account libraries,
search and persisted favourites are future work requiring separate capabilities.
Premium benefits are determined by YouTube's player, browser session and content;
Kyrion neither grants them nor promises Premium parity in an embed.

Native iframe controls handle provider errors. Embedding may be blocked by the
video owner, account/age requirements, browser restrictions or network filtering;
the direct service link remains available. Web tests using a mocked frame do not
prove that YouTube serves a particular video in a real owner session.

## References

- [YouTube player parameters](https://developers.google.com/youtube/player_parameters)
- [Embedding videos and playlists](https://support.google.com/youtube/answer/171780?hl=en)
- [YouTube developer policies guide](https://developers.google.com/youtube/terms/developer-policies-guide)
- [YouTube Music devices](https://support.google.com/youtubemusic/answer/9231765?hl=en)

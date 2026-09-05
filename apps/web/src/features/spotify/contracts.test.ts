import { describe, expect, it } from "vitest";
import { isSpotifyDeviceList, isSpotifyStatus, isSpotifyPlayback, isSpotifyPlaybackCommand, isSpotifyPlaylists, isSpotifyPlaylistCommand } from "./contracts";

describe("Spotify contracts", () => {
  it("bounds playlist results and rejects unsafe playlist commands", () => {
    const playlist = { id: "1234567890123456789012", name: "Evening", imageUrl: null, url: "https://open.spotify.com/playlist/1234567890123456789012" };
    expect(isSpotifyPlaylists({ reauthorizationRequired: false, items: [playlist] })).toBe(true);
    expect(isSpotifyPlaylists({ reauthorizationRequired: false, items: Array(7).fill(playlist) })).toBe(false);
    expect(isSpotifyPlaylists({ reauthorizationRequired: false, items: [{ ...playlist, imageUrl: "https://evil.test/image" }] })).toBe(false);
    expect(isSpotifyPlaylists({ reauthorizationRequired: false, items: [{ ...playlist, url: "javascript:alert(1)" }] })).toBe(false);
    expect(isSpotifyPlaylistCommand({ playlistId: playlist.id, deviceId: "pi" })).toBe(true);
    expect(isSpotifyPlaylistCommand({ playlistId: "spotify:playlist:anything", deviceId: "pi" })).toBe(false);
    expect(isSpotifyPlaylistCommand({ playlistId: playlist.id, deviceId: " " })).toBe(false);
  });
  it("validates bounded playback commands", () => {
    expect(isSpotifyPlaybackCommand({ action: "RESUME", deviceId: "pi" })).toBe(true);
    expect(isSpotifyPlaybackCommand({ action: "VOLUME", deviceId: "pi", volumePercent: 0 })).toBe(true);
    for (const volumePercent of [-1, 101, 0.5, "50", null]) {
      expect(isSpotifyPlaybackCommand({ action: "VOLUME", deviceId: "pi", volumePercent })).toBe(false);
    }
    expect(isSpotifyPlaybackCommand({ action: "VOLUME", deviceId: "pi" })).toBe(false);
    expect(isSpotifyPlaybackCommand({ action: "PAUSE", deviceId: "pi", volumePercent: 50 })).toBe(false);
    expect(isSpotifyPlaybackCommand({ action: "EXECUTE", deviceId: "pi" })).toBe(false);
    expect(isSpotifyPlaybackCommand({ action: "RESUME", deviceId: " " })).toBe(false);
  });
  it("accepts empty playback but rejects unsafe metadata links and malformed progress", () => {
    const playback = { playing: false, title: null, artist: null, imageUrl: null, trackUrl: null, progressMs: 0, durationMs: 0, deviceId: null, disallowed: [] };
    expect(isSpotifyPlayback(playback)).toBe(true);
    expect(isSpotifyPlayback({ ...playback, imageUrl: "https://i.scdn.co/image/album", trackUrl: "https://open.spotify.com/track/id" })).toBe(true);
    expect(isSpotifyPlayback({ ...playback, trackUrl: "javascript:alert(1)" })).toBe(false);
    expect(isSpotifyPlayback({ ...playback, imageUrl: "https://example.com/image" })).toBe(false);
    expect(isSpotifyPlayback({ ...playback, progressMs: -1 })).toBe(false);
    expect(isSpotifyPlayback({ ...playback, durationMs: Infinity })).toBe(false);
    expect(isSpotifyPlayback({ ...playback, disallowed: [true] })).toBe(false);
  });
  it("accepts bounded status and device responses", () => {
    expect(isSpotifyStatus({ configured: true, connected: true, accountName: "Flo" })).toBe(true);
    expect(isSpotifyDeviceList([{ id: "pi", name: "Kyrion Wohnzimmer", type: "Speaker", active: false, restricted: false, volumePercent: 50, supportsVolume: true }])).toBe(true);
  });
  it("rejects malformed provider data", () => {
    expect(isSpotifyStatus({ configured: "yes", connected: true, accountName: null })).toBe(false);
    expect(isSpotifyDeviceList([{ id: null }])).toBe(false);
  });
});

import { expect, it } from "vitest";
import { playbackPosition } from "./timeline";
import { isSpotifyPlaybackCommand } from "./contracts";

it("advances playing time between server snapshots, freezes paused time and stops at the duration", () => {
  expect(playbackPosition(48000, 169000, 2500, true)).toBe(50500);
  expect(playbackPosition(48000, 169000, 2500, false)).toBe(48000);
  expect(playbackPosition(168000, 169000, 2500, true)).toBe(169000);
});
it("accepts bounded seeking and rejects mixed or invalid commands", () => {
  expect(isSpotifyPlaybackCommand({ action: "SEEK", deviceId: "pi", positionMs: 65000 })).toBe(true);
  for (const positionMs of [-1, 0.5, 86400001, null, "1000"]) {
    expect(isSpotifyPlaybackCommand({ action: "SEEK", deviceId: "pi", positionMs })).toBe(false);
  }
  expect(isSpotifyPlaybackCommand({ action: "SEEK", deviceId: "pi", positionMs: 1000, volumePercent: 30 })).toBe(false);
  expect(isSpotifyPlaybackCommand({ action: "PAUSE", deviceId: "pi", positionMs: 1000 })).toBe(false);
});

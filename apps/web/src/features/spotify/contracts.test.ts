import { describe, expect, it } from "vitest";
import { isSpotifyDeviceList, isSpotifyStatus } from "./contracts";

describe("Spotify contracts", () => {
  it("accepts bounded status and device responses", () => {
    expect(isSpotifyStatus({ configured: true, connected: true, accountName: "Flo" })).toBe(true);
    expect(isSpotifyDeviceList([{ id: "pi", name: "Kyrion Wohnzimmer", type: "Speaker", active: false, restricted: false, volumePercent: 50, supportsVolume: true }])).toBe(true);
  });
  it("rejects malformed provider data", () => {
    expect(isSpotifyStatus({ configured: "yes", connected: true, accountName: null })).toBe(false);
    expect(isSpotifyDeviceList([{ id: null }])).toBe(false);
  });
});

import { describe, expect, it } from "vitest";
import { isCoreConnectionList, isCoreProviderList } from "./catalog-contracts";

describe("Core integration catalog contracts", () => {
  it("accepts local/cloud providers and rejects malformed data", () => {
    expect(isCoreProviderList([{ id: "spotify", name: "Spotify", description: "", locality: "CLOUD", authentication: "OAUTH", availability: "LIVE", capabilities: [] }])).toBe(true);
    expect(isCoreProviderList([{ id: "bad", name: "Bad", description: "", locality: "other" }])).toBe(false);
  });

  it("accepts sanitized connection summaries", () => {
    expect(isCoreConnectionList([{ providerId: "spotify", connectionId: "id", status: "CONNECTED", displayIdentity: "user@example.com", enabledCapabilities: ["media.playback"], availableCapabilities: ["media.playback"], createdAt: "", updatedAt: "", health: null }])).toBe(true);
    expect(isCoreConnectionList([{ providerId: "spotify", connectionId: "id", accessToken: "secret" }])).toBe(false);
  });
});

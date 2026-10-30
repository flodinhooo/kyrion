import { describe, expect, it } from "vitest";
import type { RuntimeDevice } from "./contracts";
import { mergeDeviceSnapshots } from "./snapshot";

const device: RuntimeDevice = { id: "lamp", provider: "home_assistant", deviceClass: "light", displayName: "Lamp",
  hardwareName: "Hue", room: null, capabilities: [{ id: "power.read" }], availability: "online",
  observedAt: "2026-10-19T10:00:00Z", state: null };

describe("device snapshot ordering", () => {
  it("keeps newer state but accepts metadata from a delayed response", () => {
    expect(mergeDeviceSnapshots([device], [{ ...device, displayName: "New name", observedAt: "2026-10-19T09:59:00Z", availability: "offline" }])[0])
      .toMatchObject({ displayName: "New name", availability: "online", observedAt: device.observedAt });
  });
  it("accepts expiry diagnostics with unchanged observation time and removes missing devices", () => {
    expect(mergeDeviceSnapshots([device], [{ ...device, availability: "unknown", diagnosticReason: "stale_observation" }])[0].availability).toBe("unknown");
    expect(mergeDeviceSnapshots([device], [])).toEqual([]);
  });
});

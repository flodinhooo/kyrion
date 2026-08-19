import { describe, expect, it } from "vitest";
import { isDeviceCommandResult, isRuntimeDeviceList } from "./contracts";

describe("runtime device contracts", () => {
  it("accepts an explicit unknown availability without an observation", () => {
    expect(isRuntimeDeviceList([{
      id: "f95ad0f2-b901-4f3b-9f14-d76884e48e29",
      provider: "nanoleaf",
      deviceClass: "light",
      displayName: "Bedroom panels",
      hardwareName: "Nanoleaf",
      room: { id: "9adb72fc-9e91-48c5-b577-881714c21167", name: "Schlafzimmer", roomType: "bedroom" },
      capabilities: [{ id: "power.set" }, { id: "light.setBrightness" }],
      availability: "unknown",
      observedAt: null,
      state: null,
    }])).toBe(true);
  });

  it("rejects invented availability values", () => {
    expect(isRuntimeDeviceList([{
      id: "device-1",
      provider: "nanoleaf",
      deviceClass: "light",
      displayName: "Panels",
      hardwareName: "Nanoleaf",
      room: null,
      capabilities: [],
      availability: "probably-online",
      observedAt: null,
      state: null,
    }])).toBe(false);
  });

  it("accepts a typed Core command result", () => {
    expect(isDeviceCommandResult({
      capability: "power.set",
      roomName: "Schlafzimmer",
      requested: 1,
      succeeded: 1,
      failed: 0,
      outcomes: [{ deviceId: "device-1", displayName: "Panels", status: "succeeded" }],
      correlationId: "correlation-1",
    })).toBe(true);
  });
});

import { describe, expect, it } from "vitest";
import { isButtonBindingList, isDeviceCommandResult, isRuntimeDeviceList } from "./contracts";

describe("button authorization contracts", () => {
  const binding = { gesture: "single", targetDeviceId: "lamp", targetRoomId: null, action: "toggle" };
  it("retains explicit legacy and current grant states for review", () => {
    expect(isButtonBindingList([{ ...binding, grantId: null }])).toBe(true);
    expect(isButtonBindingList([binding])).toBe(true);
    expect(isButtonBindingList([{ ...binding, grantId: "a1234567-1234-1234-1234-123456789012" }])).toBe(true);
  });
  it("rejects malformed grant metadata rather than showing authorization", () => {
    for (const grantId of [false, {}, "", "authorized"]) {
      expect(isButtonBindingList([{ ...binding, grantId }])).toBe(false);
    }
  });
  it("rejects ambiguous duplicate gestures and non-object rows", () => {
    expect(isButtonBindingList([binding, binding])).toBe(false);
    expect(isButtonBindingList([null])).toBe(false);
  });
});

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

import { describe, expect, it } from "vitest";
import { isActionOutcome, isWebActionRequest } from "./contracts";

const id = "9adb72fc-9e91-48c5-b577-881714c21167";

describe("action contracts", () => {
  it("accepts one bounded typed power proposal", () => {
    expect(isWebActionRequest({ idempotencyKey: id, locale: "de", proposal: {
      type: "device", targetId: id, capability: "power.set", arguments: { on: true },
    } })).toBe(true);
  });

  it("rejects extra arguments for a capability", () => {
    expect(isWebActionRequest({ idempotencyKey: id, locale: "de", proposal: {
      type: "device", targetId: id, capability: "power.set", arguments: { on: true, brightness: 50 },
    } })).toBe(false);
  });

  it("accepts a correlated Core outcome", () => {
    expect(isActionOutcome({ status: "succeeded", code: "action.succeeded", correlationId: id,
      capability: "power.set", requested: 1, succeeded: 1, failed: 0,
      targets: [{ targetId: id, displayName: "Panels", status: "succeeded" }] })).toBe(true);
  });
});

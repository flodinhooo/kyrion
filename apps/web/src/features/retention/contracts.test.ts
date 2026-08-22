import { describe, expect, it } from "vitest";
import { isRetentionPolicy } from "./contracts";

describe("retention contracts", () => {
  it("accepts only non-enforcing typed policies", () => {
    expect(isRetentionPolicy({ conversations: "keep_forever", activity: "365_days", personalMemory: "90_days", updatedAt: null, enforcementActive: false })).toBe(true);
    expect(isRetentionPolicy({ conversations: "7_days", activity: "365_days", personalMemory: "90_days", updatedAt: null, enforcementActive: false })).toBe(false);
    expect(isRetentionPolicy({ conversations: "keep_forever", activity: "365_days", personalMemory: "90_days", updatedAt: null, enforcementActive: true })).toBe(false);
  });
});

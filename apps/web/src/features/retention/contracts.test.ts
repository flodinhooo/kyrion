import { describe, expect, it } from "vitest";
import { isRetentionCleanupPreview, isRetentionPolicy } from "./contracts";

describe("retention contracts", () => {
  it("accepts only non-enforcing typed policies", () => {
    expect(isRetentionPolicy({ conversations: "keep_forever", activity: "365_days", personalMemory: "90_days", updatedAt: null, enforcementActive: false, manualCleanupAvailable: true })).toBe(true);
    expect(isRetentionPolicy({ conversations: "7_days", activity: "365_days", personalMemory: "90_days", updatedAt: null, enforcementActive: false, manualCleanupAvailable: true })).toBe(false);
    expect(isRetentionPolicy({ conversations: "keep_forever", activity: "365_days", personalMemory: "90_days", updatedAt: null, enforcementActive: true, manualCleanupAvailable: true })).toBe(false);
  });

  it("validates cleanup previews and non-negative counts", () => {
    const preview = { generatedAt: "2026-08-22T16:00:00Z", conversations: { policy: "30_days", cutoff: "2026-07-23T16:00:00Z", records: 2 }, activity: { policy: "keep_forever", cutoff: null, records: 0 }, personalMemory: { policy: "90_days", cutoff: "2026-05-24T16:00:00Z", records: 1 } };
    expect(isRetentionCleanupPreview(preview)).toBe(true);
    expect(isRetentionCleanupPreview({ ...preview, conversations: { ...preview.conversations, records: -1 } })).toBe(false);
  });
});

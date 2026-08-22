import { describe, expect, it } from "vitest";
import { isActivityIntegrityResponse } from "./contracts";

describe("activity integrity contracts", () => {
  it("accepts typed chain reports and rejects malformed counts", () => {
    const chain = { scope: "owner", valid: true, sealedEvents: 3, legacyEvents: 1, authorizedPruning: false, issues: [] };
    expect(isActivityIntegrityResponse({ owner: chain, system: { ...chain, scope: "system" } })).toBe(true);
    expect(isActivityIntegrityResponse({ owner: { ...chain, sealedEvents: "3" }, system: chain })).toBe(false);
  });
});

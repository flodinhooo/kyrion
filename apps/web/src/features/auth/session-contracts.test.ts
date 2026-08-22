import { describe, expect, it } from "vitest";
import { isActiveSessionList } from "./session-contracts";

describe("active session contracts", () => {
  it("accepts only complete typed session metadata", () => {
    expect(isActiveSessionList([{
      id: "1d111111-1111-4111-8111-111111111111",
      createdAt: "2026-08-22T12:00:00Z",
      lastSeenAt: "2026-08-22T12:30:00Z",
      expiresAt: "2026-08-29T12:00:00Z",
      current: true,
    }])).toBe(true);
    expect(isActiveSessionList([{ id: "session", tokenHash: "must-not-be-trusted" }])).toBe(false);
    expect(isActiveSessionList({ sessions: [] })).toBe(false);
  });
});

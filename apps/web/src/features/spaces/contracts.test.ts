import { describe, expect, it } from "vitest";
import { isInvitation, isSpace } from "./contracts";
import { spaceMessages } from "./messages";

describe("Space contracts", () => {
  it.each(["HOME", "BUSINESS"])("accepts %s configuration", (type) => {
    expect(isSpace({ id: "local", name: "Kyrion", type, status: "ACTIVE", defaultRoleKey: "USER" })).toBe(true);
  });
  it.each([null, {}, { type: "COMPANY" }, { id: "local", name: "Name", type: "HOME", status: "ACTIVE" }])("rejects incomplete or unknown Space data", (value) => {
    expect(isSpace(value)).toBe(false);
  });
  it.each(["ACTIVE", "REVOKED", "USED", "EXPIRED"])("recognizes %s invitation state", (status) => {
    expect(isInvitation({ id: "id", createdBy: "owner", createdAt: "2026-10-30", expiresAt: "2026-10-31", roleKey: "VIEWER", maxUses: 1, useCount: 0, status })).toBe(true);
  });
  it("rejects malformed invitation data", () => {
    expect(isInvitation({ id: "id", roleKey: "USER", expiresAt: "invalid", maxUses: 1, useCount: 0, status: "ACTIVE" })).toBe(false);
  });
  it("keeps German and English resources aligned", () => {
    expect(Object.keys(spaceMessages.de).sort()).toEqual(Object.keys(spaceMessages.en).sort());
    expect(Object.keys(spaceMessages.de.statuses)).toEqual(Object.keys(spaceMessages.en.statuses));
  });
});

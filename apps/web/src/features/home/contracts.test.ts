import { describe, expect, it } from "vitest";
import { isRoom } from "./contracts";

describe("room contracts", () => {
  it("accepts a bounded room type", () => {
    expect(isRoom({ id: "room-1", name: "Setup", roomType: "office", createdAt: "now", updatedAt: "now" })).toBe(true);
  });

  it("rejects an unknown room type", () => {
    expect(isRoom({ id: "room-1", name: "Setup", roomType: "spaceship", createdAt: "now", updatedAt: "now" })).toBe(false);
  });
});

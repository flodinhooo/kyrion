import { describe, expect, it } from "vitest";
import { hsvToHex } from "./color";

describe("hsvToHex", () => {
  it("converts observed primary colours", () => {
    expect(hsvToHex(0, 100)).toBe("#ff0000");
    expect(hsvToHex(120, 100)).toBe("#00ff00");
    expect(hsvToHex(240, 100)).toBe("#0000ff");
  });

  it("preserves white and normalizes hue", () => {
    expect(hsvToHex(80, 0)).toBe("#ffffff");
    expect(hsvToHex(360, 100)).toBe("#ff0000");
    expect(hsvToHex(null, null)).toBe("#ffffff");
  });
});

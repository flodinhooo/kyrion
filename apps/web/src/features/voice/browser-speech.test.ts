import { afterEach, describe, expect, it, vi } from "vitest";
import { availableBrowserVoices } from "./browser-speech";

afterEach(() => vi.unstubAllGlobals());
describe("optional browser speech", () => {
  it("keeps the platform usable when speech synthesis is unavailable", () => {
    vi.stubGlobal("window", {});
    expect(availableBrowserVoices()).toEqual([]);
  });
});

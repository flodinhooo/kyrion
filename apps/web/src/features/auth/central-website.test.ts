import { describe, expect, it } from "vitest";
import { centralWebsite } from "./central-website";

describe("official linking entry", () => {
  it("opens the correct code-entry tab for each language", () => {
    expect(centralWebsite("https://auth.kyrion.ch/realms/kyrion/device", "de")).toBe("https://www.kyrion.ch/connect");
    expect(centralWebsite("https://auth.kyrion.ch/realms/kyrion/device", "en")).toBe("https://www.kyrion.ch/en/connect");
  });
  it("keeps independent and isolated providers on their own verification page", () => {
    for (const url of ["http://localhost:18089/realms/kyrion/device", "https://auth.kyrion.ch.evil.test/realms/kyrion/device", "https://auth.kyrion.ch/realms/other/device", "not-a-url"])
      expect(centralWebsite(url, "de")).toBeNull();
  });
});

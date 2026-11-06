import { describe, expect, it } from "vitest";
import { isCentralDevice, isCentralStatus } from "./central-contracts";
import { centralMessages } from "./central-messages";

const device = { userCode: "ABCD-EFGH", verificationUri: "https://auth.example/realms/kyrion/device", expiresAt: "2026-11-07T00:00:00Z", interval: 5 };
describe("central identity contracts", () => {
  it("accepts validated provider links and loopback development", () => {
    expect(isCentralDevice(device)).toBe(true);
    expect(isCentralDevice({ ...device, verificationUri: "http://localhost:8089/realms/kyrion/device" })).toBe(true);
  });
  it.each(["javascript:alert(1)", "http://192.168.1.1/device", "https://user:secret@auth.example/device", "https://auth.example/#token", "/device"])("rejects unsafe provider link %s", (verificationUri) => {
    expect(isCentralDevice({ ...device, verificationUri })).toBe(false);
  });
  it("rejects malformed timing and identity status", () => {
    expect(isCentralDevice({ ...device, interval: 0 })).toBe(false);
    expect(isCentralDevice({ ...device, interval: Infinity })).toBe(false);
    expect(isCentralDevice({ ...device, expiresAt: "bad" })).toBe(false);
    expect(isCentralStatus({ linked: true, issuer: "https://auth.example" })).toBe(true);
    expect(isCentralStatus({ linked: "true" })).toBe(false);
  });
  it("provides matching German and English messages and errors", () => {
    expect(Object.keys(centralMessages.de).sort()).toEqual(Object.keys(centralMessages.en).sort());
    expect(Object.keys(centralMessages.de.errors).sort()).toEqual(Object.keys(centralMessages.en.errors).sort());
  });
});

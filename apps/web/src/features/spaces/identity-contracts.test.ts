import { describe, expect, it } from "vitest";
import { isBusinessPolicy, isDnsChallenge, isEmailIdentity } from "./identity-contracts";
import { identityMessages } from "./identity-messages";

describe("Business identity contracts", () => {
  it.each(["MISSING", "PENDING", "VERIFIED", "LOCALLY_ATTESTED"])("recognizes %s without equating local proof with SMTP", (status) => {
    expect(isEmailIdentity({ email: null, pendingEmail: null, status, smtpAvailable: false })).toBe(true);
  });
  it("rejects an invented successful status and incomplete response", () => {
    expect(isEmailIdentity({ status: "SUCCESS" })).toBe(false);
    expect(isEmailIdentity({ email: {}, pendingEmail: null, status: "VERIFIED", smtpAvailable: true })).toBe(false);
  });
  it("validates policy proof metadata", () => {
    expect(isBusinessPolicy({ mode: "STRICT", recoveryConfigured: true, domains: [{ domain: "company.ch", allowed: true, status: "VERIFIED", verifiedUntil: "2026-11-30" }] })).toBe(true);
    expect(isBusinessPolicy({ mode: "SSO", recoveryConfigured: true, domains: [] })).toBe(false);
    expect(isBusinessPolicy({ mode: "STRICT", recoveryConfigured: false, domains: [{}] })).toBe(false);
  });
  it("requires an expiring DNS challenge", () => {
    expect(isDnsChallenge({ name: "_kyrion-verification.company.ch", value: "proof", expiresAt: "2026-11-01T12:00:00Z" })).toBe(true);
    expect(isDnsChallenge({ name: "record", value: "proof", expiresAt: "invalid" })).toBe(false);
  });
  it("keeps both locales and error codes aligned", () => {
    expect(Object.keys(identityMessages.en).sort()).toEqual(Object.keys(identityMessages.de).sort());
    expect(Object.keys(identityMessages.en.errors).sort()).toEqual(Object.keys(identityMessages.de.errors).sort());
  });
});

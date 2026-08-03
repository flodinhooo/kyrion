import { describe, expect, it } from "vitest";
import { csrfCookieOptions, csrfTokensMatch, sessionCookieOptions } from "./auth-security";

describe("authentication boundary", () => {
  it("accepts only identical non-empty CSRF tokens", () => {
    expect(csrfTokensMatch("secret-token", "secret-token")).toBe(true);
    expect(csrfTokensMatch("secret-token", "different-token")).toBe(false);
    expect(csrfTokensMatch("short", "longer")).toBe(false);
    expect(csrfTokensMatch(undefined, "secret-token")).toBe(false);
    expect(csrfTokensMatch("secret-token", null)).toBe(false);
  });

  it("keeps the session credential inaccessible to browser scripts", () => {
    const expires = new Date("2026-08-10T20:00:00Z");
    expect(sessionCookieOptions(expires, false)).toEqual({
      httpOnly: true, sameSite: "strict", secure: false, path: "/", expires,
    });
    expect(sessionCookieOptions(expires, true).secure).toBe(true);
  });

  it("uses a readable but non-authenticating CSRF cookie with strict same-site policy", () => {
    const options = csrfCookieOptions(new Date("2026-08-10T20:00:00Z"), true);
    expect(options.httpOnly).toBe(false);
    expect(options.sameSite).toBe("strict");
    expect(options.secure).toBe(true);
    expect(options.path).toBe("/");
  });
});

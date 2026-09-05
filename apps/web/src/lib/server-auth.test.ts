import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const cookie = vi.hoisted(() => ({ value: "review-session" as string | undefined }));
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => cookie.value ? { value: cookie.value } : undefined }) }));
vi.mock("@/lib/auth-security", () => ({ csrfTokensMatch: () => false }));
import { requireApiSession } from "./server-auth";

describe("session availability", () => {
  beforeEach(() => { cookie.value = "review-session"; });
  afterEach(() => vi.unstubAllGlobals());
  it("does not contact Core without a session", async () => {
    cookie.value = undefined;
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    const result = await requireApiSession();
    expect(result).toBeInstanceOf(Response);
    expect((result as Response).status).toBe(401);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("distinguishes expired sessions from an unavailable authority", async () => {
    for (const status of [401, 503]) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({}, { status })));
      const result = await requireApiSession() as Response;
      expect(result.status).toBe(status);
      expect(await result.json()).toEqual({ code: status === 401 ? "UNAUTHENTICATED" : "CORE_UNAVAILABLE" });
    }
  });
  it("treats network failures and malformed successful responses as unavailable", async () => {
    for (const fetcher of [vi.fn().mockRejectedValue(new TypeError("offline")), vi.fn().mockResolvedValue(Response.json({}))]) {
      vi.stubGlobal("fetch", fetcher);
      expect((await requireApiSession() as Response).status).toBe(503);
    }
  });
  it("returns the authenticated identity with a bounded request", async () => {
    const user = { id: "owner", username: "review" };
    const fetcher = vi.fn().mockResolvedValue(Response.json(user)); vi.stubGlobal("fetch", fetcher);
    expect(await requireApiSession()).toEqual({ token: "review-session", user });
    expect(fetcher.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
  });
});

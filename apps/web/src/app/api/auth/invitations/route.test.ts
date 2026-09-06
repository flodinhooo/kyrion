import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({ csrf: true, authenticated: true }));
vi.mock("@/lib/server-auth", () => ({
  CORE_SERVICE_URL: "http://core.test",
  csrfIsValid: async () => auth.csrf,
  requireApiSession: async () => auth.authenticated
    ? { token: "private-session-token", user: { id: "owner", username: "owner" } }
    : Response.json({ code: "UNAUTHENTICATED" }, { status: 401 }),
}));
import { POST } from "./route";

describe("invitation boundary", () => {
  beforeEach(() => { auth.csrf = true; auth.authenticated = true; });
  afterEach(() => vi.unstubAllGlobals());

  it("requires CSRF and an authenticated session before contacting Core", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    auth.csrf = false;
    expect((await POST(new Request("http://web.test"))).status).toBe(403);
    auth.csrf = true; auth.authenticated = false;
    expect((await POST(new Request("http://web.test"))).status).toBe(401);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("preserves Core's denial for invited users", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ code: "INVITATION_FORBIDDEN" }, { status: 403 })));
    const response = await POST(new Request("http://web.test"));
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ code: "INVITATION_FORBIDDEN" });
  });

  it("returns the one-time code without caching it or exposing session credentials", async () => {
    const invitation = { code: "a".repeat(43), expiresAt: "2026-09-07T12:00:00Z" };
    const fetcher = vi.fn().mockResolvedValue(Response.json(invitation, { status: 201 }));
    vi.stubGlobal("fetch", fetcher);
    const response = await POST(new Request("http://web.test"));
    expect(response.status).toBe(201);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(await response.json()).toEqual(invitation);
    expect(fetcher.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
  });
});

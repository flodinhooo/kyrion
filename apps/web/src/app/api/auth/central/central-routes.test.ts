import { beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({
  set: vi.fn(), get: vi.fn(), csrf: vi.fn(), auth: vi.fn(), token: vi.fn(), setAuth: vi.fn(),
}));
vi.mock("next/headers", () => ({ cookies: async () => ({ set: mocks.set, get: mocks.get }) }));
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.test", csrfIsValid: mocks.csrf, requireApiSession: mocks.auth, sessionToken: mocks.token, secureCookie: () => true }));
vi.mock("../session-cookie", () => ({ setAuthCookies: mocks.setAuth }));
import { GET, POST, DELETE } from "./[action]/route";

const context = (action: string) => ({ params: Promise.resolve({ action }) });
const request = (action: string, body: unknown = {}, method = "POST", origin = "https://web.test") => new Request(`https://web.test/api/auth/central/${action}`, {
  method, headers: { Origin: origin, "Content-Type": "application/json" }, body: JSON.stringify(body),
});
describe("central identity BFF", () => {
  beforeEach(() => {
    vi.resetAllMocks(); mocks.csrf.mockResolvedValue(true); mocks.token.mockResolvedValue(null);
    mocks.auth.mockResolvedValue({ token: "local-session", user: { id: "local-user" } });
  });
  it("allows only known endpoints and methods", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch");
    expect((await POST(request("setup"), context("setup"))).status).toBe(404);
    expect((await DELETE(request("start", {}, "DELETE"), context("start"))).status).toBe(404);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("requires CSRF and matching origin even for anonymous login", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch");
    mocks.csrf.mockResolvedValue(false);
    expect((await POST(request("start", { mode: "LOGIN" }), context("start"))).status).toBe(403);
    mocks.csrf.mockResolvedValue(true);
    expect((await POST(request("start", { mode: "LOGIN" }, "POST", "https://evil.test"), context("start"))).status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("keeps the operation credential exclusively in an HttpOnly cookie", async () => {
    const device = { userCode: "CODE-1234", verificationUri: "https://auth.example/device", interval: 5, expiresAt: "2026-11-07T00:00:00Z" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ ...device, operationToken: "secret-operation" }));
    const response = await POST(request("start", { mode: "LOGIN" }), context("start"));
    expect(await response.json()).toEqual(device);
    expect(mocks.set).toHaveBeenCalledWith("kyrion_central_operation", "secret-operation", expect.objectContaining({ httpOnly: true, secure: true, sameSite: "strict", path: "/api/auth/central" }));
  });
  it("uses the browser Host when Next normalizes the internal request hostname", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ userCode: "CODE-1234", verificationUri: "https://auth.example/device", interval: 5, expiresAt: "2026-11-07T00:00:00Z", operationToken: "secret" }));
    const internalRequest = new Request("http://localhost:3209/api/auth/central/start", {
      method: "POST", headers: { Host: "127.0.0.1:3209", Origin: "http://127.0.0.1:3209", "Content-Type": "application/json" }, body: JSON.stringify({ mode: "LOGIN" }),
    });
    expect((await POST(internalRequest, context("start"))).status).toBe(200);
  });
  it("never trusts an operation credential supplied in browser JSON", async () => {
    mocks.get.mockReturnValue(undefined);
    const fetcher = vi.spyOn(globalThis, "fetch");
    expect((await POST(request("poll", { operationToken: "foreign-operation" }), context("poll"))).status).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("passes the session bound operation cookie and hides the new session token", async () => {
    mocks.get.mockReturnValue({ value: "bound-operation" });
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ user: { id: "owner" }, sessionToken: "private-session", expiresAt: "2026-11-07T00:00:00Z" }));
    const response = await POST(request("complete", { operationToken: "attacker-operation", confirm: true }), context("complete"));
    expect(fetcher).toHaveBeenCalledWith("http://core.test/v1/auth/central/complete", expect.objectContaining({ body: JSON.stringify({ operationToken: "bound-operation", confirm: true }) }));
    expect(mocks.setAuth).toHaveBeenCalledWith("private-session", "2026-11-07T00:00:00Z");
    expect(await response.json()).toEqual({ completed: true });
    expect(mocks.set).toHaveBeenCalledWith("kyrion_central_operation", "", expect.objectContaining({ path: "/api/auth/central", maxAge: 0 }));
  });
  it("requires a local session for link mutations and preserves password only in the request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    const response = await DELETE(request("link", { currentPassword: "local-password" }, "DELETE"), context("link"));
    expect(mocks.auth).toHaveBeenCalledOnce();
    expect(response.status).toBe(204);
  });
  it("reads optional config without cloud or a local authentication lookup", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ enabled: false, sessionToken: "must-never-forward" }));
    const response = await GET(new Request("https://web.test/api/auth/central/config"), context("config"));
    expect(await response.json()).toEqual({ enabled: false });
    expect(mocks.auth).not.toHaveBeenCalled();
  });
});

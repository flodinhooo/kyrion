import { beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.local", csrfIsValid: vi.fn(), requireApiSession: vi.fn() }));
import { csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { spaceProxy } from "./proxy";

describe("Space same-origin proxy", () => {
  beforeEach(() => { vi.resetAllMocks(); vi.stubGlobal("fetch", vi.fn()); });
  it.each(["PUT", "POST", "DELETE"])("requires CSRF for %s", async (method) => {
    vi.mocked(csrfIsValid).mockResolvedValue(false);
    const response = await spaceProxy(new Request("http://local/api/space", { method }), "/v1/space");
    expect(response.status).toBe(403); expect(fetch).not.toHaveBeenCalled();
  });
  it("requires an authenticated session for reads", async () => {
    vi.mocked(requireApiSession).mockResolvedValue(Response.json({ code: "UNAUTHENTICATED" }, { status: 401 }));
    expect((await spaceProxy(new Request("http://local/api/space"), "/v1/space")).status).toBe(401);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("forwards only the server session to the local Core", async () => {
    vi.mocked(requireApiSession).mockResolvedValue({ token: "server-token", user: { id: "actor", username: "actor" } });
    vi.mocked(fetch).mockResolvedValue(Response.json({ name: "Home" }));
    const response = await spaceProxy(new Request("http://local/api/space"), "/v1/space");
    expect(fetch).toHaveBeenCalledWith("http://core.local/v1/space", expect.objectContaining({ cache: "no-store", headers: expect.objectContaining({ Authorization: "Bearer server-token" }) }));
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  });
  it("returns a bounded offline error", async () => {
    vi.mocked(requireApiSession).mockResolvedValue({ token: "server-token", user: { id: "actor", username: "actor" } });
    vi.mocked(fetch).mockRejectedValue(new Error("offline"));
    expect((await spaceProxy(new Request("http://local/api/space"), "/v1/space")).status).toBe(503);
  });
});

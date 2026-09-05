import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-auth", () => ({
  CORE_SERVICE_URL: "http://core.test",
  requireApiSession: vi.fn(),
  csrfIsValid: vi.fn(),
}));

import { csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { GET, PUT } from "./route";

const fetchMock = vi.fn<typeof fetch>();
const request = (body: unknown) => new Request("http://web.test/api/integrations/spotify/playback", {
  method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(requireApiSession).mockResolvedValue({ token: "server-only-token", user: { id: "owner", username: "Owner" } });
  vi.mocked(csrfIsValid).mockResolvedValue(true);
});
afterEach(() => { vi.resetAllMocks(); vi.unstubAllGlobals(); });

describe("Spotify playback boundary", () => {
  it("requires an owner session for reads and writes", async () => {
    vi.mocked(requireApiSession).mockResolvedValue(Response.json({ code: "UNAUTHENTICATED" }, { status: 401 }));
    expect((await GET()).status).toBe(401);
    expect((await PUT(request({ action: "PAUSE", deviceId: "pi" }))).status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("rejects commands without CSRF validation", async () => {
    vi.mocked(csrfIsValid).mockResolvedValue(false);
    expect((await PUT(request({ action: "PAUSE", deviceId: "pi" }))).status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("rejects invalid commands before reaching Core", async () => {
    expect((await PUT(request({ action: "VOLUME", deviceId: "pi", volumePercent: 100.5 }))).status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("forwards valid commands with the server session only", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    const response = await PUT(request({ action: "RESUME", deviceId: "pi" }));
    expect(response.status).toBe(204);
    expect(await response.text()).toBe("");
    expect(fetchMock).toHaveBeenCalledWith("http://core.test/v1/integrations/spotify/playback", expect.objectContaining({
      method: "PUT", headers: { Authorization: "Bearer server-only-token", "Content-Type": "application/json" },
      body: JSON.stringify({ action: "RESUME", deviceId: "pi" }),
    }));
  });
  it("preserves Core errors and reports unavailable Core", async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ code: "SPOTIFY_PROVIDER_ERROR" }, { status: 502 }));
    const response = await PUT(request({ action: "PAUSE", deviceId: "pi" }));
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ code: "SPOTIFY_PROVIDER_ERROR" });
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    expect((await GET()).status).toBe(503);
  });
});

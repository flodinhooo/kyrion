import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.test", requireApiSession: vi.fn(), csrfIsValid: vi.fn() }));
import { csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { POST } from "./route";

const fetchMock = vi.fn<typeof fetch>();
const request = () => new Request("http://web.test/api/integrations/youtube/embed", { method: "POST", body: JSON.stringify({ url: "https://youtu.be/M7lc1UVf-VE", source: "VIDEO" }) });
beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(requireApiSession).mockResolvedValue({ token: "server-token", user: { id: "owner", username: "Owner" } });
  vi.mocked(csrfIsValid).mockResolvedValue(true);
});
afterEach(() => { vi.resetAllMocks(); vi.unstubAllGlobals(); });

describe("YouTube embed preparation", () => {
  it("requires authentication and CSRF before invoking Core", async () => {
    vi.mocked(csrfIsValid).mockResolvedValue(false);
    expect((await POST(request())).status).toBe(403);
    vi.mocked(requireApiSession).mockResolvedValue(new Response(null, { status: 401 }));
    expect((await POST(request())).status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("returns only validated embed metadata", async () => {
    const value = { embedUrl: "https://www.youtube-nocookie.com/embed/M7lc1UVf-VE?autoplay=0", watchUrl: "https://www.youtube.com/watch?v=M7lc1UVf-VE" };
    fetchMock.mockResolvedValueOnce(Response.json(value));
    expect(await (await POST(request())).json()).toEqual(value);
    expect(fetchMock).toHaveBeenCalledWith("http://core.test/v1/integrations/youtube/embed", expect.objectContaining({ headers: { Authorization: "Bearer server-token", "Content-Type": "application/json" } }));
    fetchMock.mockResolvedValueOnce(Response.json({ ...value, embedUrl: "https://evil.test" }));
    expect((await POST(request())).status).toBe(502);
  });
  it("returns Core link errors and handles an unavailable Core", async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ code: "YOUTUBE_INVALID_LINK" }, { status: 400 }));
    expect((await POST(request())).status).toBe(400);
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    expect((await POST(request())).status).toBe(503);
  });
});

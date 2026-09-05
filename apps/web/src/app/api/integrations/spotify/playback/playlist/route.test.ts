import { afterEach, beforeEach, expect, it, vi } from "vitest";
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.test", requireApiSession: vi.fn(), csrfIsValid: vi.fn() }));
import { csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { PUT } from "./route";

const fetchMock = vi.fn<typeof fetch>();
const request = (playlistId = "1234567890123456789012") => new Request("http://web.test/api/integrations/spotify/playback/playlist", { method: "PUT", body: JSON.stringify({ playlistId, deviceId: "pi" }) });
beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(requireApiSession).mockResolvedValue({ token: "server-only", user: { id: "owner", username: "Owner" } });
  vi.mocked(csrfIsValid).mockResolvedValue(true);
});
afterEach(() => { vi.resetAllMocks(); vi.unstubAllGlobals(); });

it("requires an owner, CSRF and a bounded playlist identifier", async () => {
  expect((await PUT(request("invalid"))).status).toBe(400);
  vi.mocked(csrfIsValid).mockResolvedValue(false);
  expect((await PUT(request())).status).toBe(403);
  vi.mocked(requireApiSession).mockResolvedValue(new Response(null, { status: 401 }));
  expect((await PUT(request())).status).toBe(401);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("sends one playlist command to Core and never retries a failed write", async () => {
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
  expect((await PUT(request())).status).toBe(204);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  fetchMock.mockRejectedValueOnce(new Error("offline"));
  expect((await PUT(request())).status).toBe(503);
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

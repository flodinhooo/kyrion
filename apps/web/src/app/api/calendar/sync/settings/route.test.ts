import { beforeEach, expect, it, vi } from "vitest";
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.test", requireApiSession: vi.fn(), csrfIsValid: vi.fn() }));
import { requireApiSession, csrfIsValid } from "@/lib/server-auth";
import { GET, PUT } from "./route";

beforeEach(() => {
  vi.restoreAllMocks();
  vi.mocked(requireApiSession).mockResolvedValue({ token: "private", user: { id: "owner", username: "Owner" } });
  vi.mocked(csrfIsValid).mockResolvedValue(true);
});
it("reading preferences never opts the user into synchronization", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ enabled: false, intervalSeconds: 300 }));
  expect((await GET()).status).toBe(200);
  expect(fetch).toHaveBeenCalledExactlyOnceWith("http://core.test/v1/calendar/sync/settings", expect.objectContaining({ method: "GET" }));
  expect(fetch.mock.calls[0][1]?.body).toBeUndefined();
});
it("requires CSRF for explicit opt in", async () => {
  vi.mocked(csrfIsValid).mockResolvedValue(false);
  const fetch = vi.spyOn(globalThis, "fetch");
  expect((await PUT(new Request("http://web.test/api/calendar/sync/settings", { method: "PUT", body: JSON.stringify({ enabled: true, intervalSeconds: 300 }) }))).status).toBe(403);
  expect(fetch).not.toHaveBeenCalled();
});
it("rejects an unauthenticated preference read before reaching Core", async () => {
  vi.mocked(requireApiSession).mockResolvedValue(Response.json({ code: "UNAUTHENTICATED" }, { status: 401 }));
  const fetch = vi.spyOn(globalThis, "fetch");
  expect((await GET()).status).toBe(401);
  expect(fetch).not.toHaveBeenCalled();
});

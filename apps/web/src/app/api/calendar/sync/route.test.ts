import { beforeEach, expect, it, vi } from "vitest";
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.test", requireApiSession: vi.fn(), csrfIsValid: vi.fn() }));
import { requireApiSession, csrfIsValid } from "@/lib/server-auth";
import { POST } from "./route";

beforeEach(() => {
  vi.restoreAllMocks();
  vi.mocked(requireApiSession).mockResolvedValue({ token: "private", user: { id: "owner", username: "Owner" } });
  vi.mocked(csrfIsValid).mockResolvedValue(true);
});
const request = () => new Request("http://web.test/api/calendar/sync", { method: "POST" });
it("forwards an explicit sync with server-only credentials", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ synchronized: 1, conflicts: 0, failed: 0 }));
  expect((await POST(request())).status).toBe(200);
  expect(fetch).toHaveBeenCalledWith("http://core.test/v1/calendar/sync", expect.objectContaining({ method: "POST", headers: { Authorization: "Bearer private" } }));
});
it("rejects CSRF before invoking synchronization", async () => {
  vi.mocked(csrfIsValid).mockResolvedValue(false);
  const fetch = vi.spyOn(globalThis, "fetch");
  expect((await POST(request())).status).toBe(403);
  expect(fetch).not.toHaveBeenCalled();
});
it("preserves Core permission rejection", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ code: "FORBIDDEN" }, { status: 403 }));
  expect((await POST(request())).status).toBe(403);
});

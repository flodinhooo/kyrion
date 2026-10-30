import {afterEach, beforeEach, expect, it, vi} from "vitest";

vi.mock("@/lib/server-auth", () => ({
  CORE_SERVICE_URL: "http://core.test",
  requireApiSession: vi.fn(async () => ({token: "synthetic-session"})),
  csrfIsValid: vi.fn(async () => true),
}));
import {GET, PUT} from "./route";
import {csrfIsValid, requireApiSession} from "@/lib/server-auth";

const context = (operation: string) => ({params: Promise.resolve({operation})});
beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());

it("forwards authenticated preferences without exposing the session credential", async () => {
  const upstream = vi.fn(async () => Response.json({preferences: {}}));
  vi.stubGlobal("fetch", upstream);
  const response = await GET(new Request("http://web/api/ai/preferences"), context("preferences"));
  expect(response.status).toBe(200);
  expect(upstream.mock.calls[0]).toEqual(["http://core.test/v1/ai/preferences", expect.objectContaining({
    headers: expect.objectContaining({Authorization: "Bearer synthetic-session"}),
  })]);
  expect(await response.text()).not.toContain("synthetic-session");
});

it("requires sessions, CSRF and fixed operations before contacting Core", async () => {
  const upstream = vi.fn();
  vi.stubGlobal("fetch", upstream);
  vi.mocked(requireApiSession).mockResolvedValueOnce(Response.json({code: "UNAUTHENTICATED"}, {status: 401}));
  expect((await GET(new Request("http://web"), context("usage"))).status).toBe(401);
  vi.mocked(csrfIsValid).mockResolvedValueOnce(false);
  expect((await PUT(new Request("http://web", {method: "PUT", body: "{}"}), context("policy"))).status).toBe(403);
  expect((await GET(new Request("http://web"), context("../secrets"))).status).toBe(404);
  expect((await PUT(new Request("http://web", {method: "PUT"}), context("usage"))).status).toBe(404);
  expect(upstream).not.toHaveBeenCalled();
});

it("preserves Core RBAC refusals and bounds settings requests", async () => {
  const upstream = vi.fn(async () => Response.json({code: "FORBIDDEN"}, {status: 403}));
  vi.stubGlobal("fetch", upstream);
  expect((await PUT(new Request("http://web", {method: "PUT", body: "{}"}), context("policy"))).status).toBe(403);
  expect((await PUT(new Request("http://web", {
    method: "PUT",
    body: "x".repeat(64001)
  }), context("preferences"))).status).toBe(400);
  expect(upstream).toHaveBeenCalledTimes(1);
});

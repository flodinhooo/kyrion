import {afterEach, beforeEach, expect, it, vi} from "vitest";

vi.mock("@/lib/server-auth", () => ({
  CORE_SERVICE_URL: "http://core.test",
  requireApiSession: vi.fn(async () => ({token: "synthetic"})),
  csrfIsValid: vi.fn(async () => true),
}));
import {PUT} from "./route";
import {GET} from "../context/route";
import {PATCH} from "../[id]/validity/route";
import {csrfIsValid, requireApiSession} from "@/lib/server-auth";

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());

it("requires authentication and CSRF before changing personal context", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  vi.mocked(requireApiSession).mockResolvedValueOnce(Response.json({}, {status: 401}));
  expect((await GET(new Request("http://web/api/memory/context"))).status).toBe(401);
  vi.mocked(csrfIsValid).mockResolvedValueOnce(false);
  expect((await PUT(new Request("http://web", {method: "PUT", body: "{}"}))).status).toBe(403);
  expect(fetcher).not.toHaveBeenCalled();
});

it("forwards settings with a server credential and preserves Core ownership refusals", async () => {
  const fetcher = vi.fn(async () => Response.json({code: "MEMORY_NOT_FOUND"}, {status: 404}));
  vi.stubGlobal("fetch", fetcher);
  const response = await PATCH(new Request("http://web", {method: "PATCH", body: '{"active":false}'}), {
    params: Promise.resolve({id: "11111111-1111-4111-8111-111111111111"}),
  });
  expect(response.status).toBe(404);
  expect(fetcher.mock.calls[0]).toEqual([expect.stringContaining("/validity"), expect.objectContaining({
    headers: expect.objectContaining({Authorization: "Bearer synthetic"}),
  })]);
  expect(await response.text()).not.toContain("synthetic");
});

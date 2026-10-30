import {beforeEach, expect, it, vi} from "vitest";

vi.mock("@/lib/server-auth", () => ({
  CORE_SERVICE_URL: "http://core.test", requireApiSession: vi.fn(), csrfIsValid: vi.fn(),
}));
import {requireApiSession, csrfIsValid} from "@/lib/server-auth";
import {DELETE} from "./route";

beforeEach(() => {
  vi.restoreAllMocks();
  vi.mocked(requireApiSession).mockResolvedValue({token: "server-only", user: {id: "owner", username: "Owner"}});
  vi.mocked(csrfIsValid).mockResolvedValue(true);
});
const context = () => ({params: Promise.resolve({id: "test-event"})});
const request = () => new Request("http://web.test/api/calendar/events/test-event?revision=7", {method: "DELETE"});

it.each([200, 204])("acknowledges Core's successful empty %s without a false unavailable error", async (status) => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, {status}));
  const response = await DELETE(request(), context());
  expect(response.status).toBe(204);
  expect(await response.text()).toBe("");
  expect(fetcher).toHaveBeenCalledWith("http://core.test/v1/calendar/events/test-event?revision=7",
    expect.objectContaining({method: "DELETE", headers: {Authorization: "Bearer server-only"}}));
});

it("preserves stale-revision conflicts", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({code: "CALENDAR_SYNC_CONFLICT"}, {status: 409}));
  const response = await DELETE(request(), context());
  expect(response.status).toBe(409);
  expect(await response.json()).toEqual({code: "CALENDAR_SYNC_CONFLICT"});
});

it("does not send a deletion without valid CSRF", async () => {
  vi.mocked(csrfIsValid).mockResolvedValue(false);
  const fetcher = vi.spyOn(globalThis, "fetch");
  expect((await DELETE(request(), context())).status).toBe(403);
  expect(fetcher).not.toHaveBeenCalled();
});

it("does not send a deletion without a session", async () => {
  vi.mocked(requireApiSession).mockResolvedValue(Response.json({code: "UNAUTHENTICATED"}, {status: 401}));
  const fetcher = vi.spyOn(globalThis, "fetch");
  expect((await DELETE(request(), context())).status).toBe(401);
  expect(fetcher).not.toHaveBeenCalled();
});

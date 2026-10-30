import {beforeEach, expect, it, vi} from "vitest";

vi.mock("@/lib/server-auth", () => ({
  CORE_SERVICE_URL: "http://core.test", requireApiSession: vi.fn(), csrfIsValid: vi.fn(),
}));
import {requireApiSession} from "@/lib/server-auth";
import {GET} from "./route";

beforeEach(() => {
  vi.restoreAllMocks();
  vi.mocked(requireApiSession).mockResolvedValue({token: "server-only", user: {id: "owner", username: "Owner"}});
});

it("preserves selected calendars and timezone-offset ranges instead of silently using primary", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({items: []}));
  const query = new URLSearchParams({
    calendarId: "secondary@example.test",
    start: "2026-10-31T09:00:00+01:00", end: "2026-10-31T22:00:00+01:00", unexpected: "discard"
  });
  expect((await GET(new Request(`http://web.test/api/integrations/google/calendar/events?${query}`))).status).toBe(200);
  const actual = new URL(String(fetcher.mock.calls[0][0]));
  expect(actual.searchParams.get("calendarId")).toBe("secondary@example.test");
  expect(actual.searchParams.get("start")).toBe("2026-10-31T09:00:00+01:00");
  expect(actual.searchParams.get("end")).toBe("2026-10-31T22:00:00+01:00");
  expect(actual.searchParams.has("unexpected")).toBe(false);
  expect(fetcher.mock.calls[0][1]).toMatchObject({headers: {Authorization: "Bearer server-only"}, cache: "no-store"});
});

it("preserves the default range when filters are omitted", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({items: []}));
  await GET();
  expect(fetcher.mock.calls[0][0]).toBe("http://core.test/v1/integrations/google/calendar/events");
});

it("reports a real provider authorization failure without initiating OAuth", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json(
    {code: "GOOGLE_REAUTHORIZATION_REQUIRED"}, {status: 409}));
  const response = await GET();
  expect(response.status).toBe(409);
  expect(await response.json()).toEqual({code: "GOOGLE_REAUTHORIZATION_REQUIRED"});
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("does not contact Google/Core without a Web session", async () => {
  vi.mocked(requireApiSession).mockResolvedValue(Response.json({code: "UNAUTHENTICATED"}, {status: 401}));
  const fetcher = vi.spyOn(globalThis, "fetch");
  expect((await GET()).status).toBe(401);
  expect(fetcher).not.toHaveBeenCalled();
});

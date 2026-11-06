import { beforeEach, expect, it, vi } from "vitest";
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.test", requireApiSession: vi.fn(), csrfIsValid: vi.fn() }));
import { requireApiSession, csrfIsValid } from "@/lib/server-auth";
import { DELETE, PUT } from "./route";

beforeEach(() => {
  vi.restoreAllMocks();
  vi.mocked(requireApiSession).mockResolvedValue({ token: "private", user: { id: "owner", username: "Owner" } });
  vi.mocked(csrfIsValid).mockResolvedValue(true);
});
const context = () => ({ params: Promise.resolve({ eventId: "event" }) });
it("preserves selected-calendar identity and conditional deletion version", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  const query = new URLSearchParams({ calendarId: "selected@example.com", etag: '"v2"' });
  expect((await DELETE(new Request(`http://web.test/api/integrations/google/calendar/events/event?${query}`, { method: "DELETE" }), context())).status).toBe(204);
  expect(fetch.mock.calls[0][0]).toBe(`http://core.test/v1/integrations/google/calendar/events/event?${query}`);
});
it("forwards conditional edits and reports conflicts instead of success", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ code: "CALENDAR_SYNC_CONFLICT" }, { status: 409 }));
  const body = { calendarId: "selected", summary: "Edit", start: "2026-10-19T09:00:00Z", end: "2026-10-19T10:00:00Z", etag: '"v1"' };
  const response = await PUT(new Request("http://web.test/api/integrations/google/calendar/events/event", { method: "PUT", body: JSON.stringify(body) }), context());
  expect(response.status).toBe(409);
  expect(fetch.mock.calls[0][1]?.body).toBe(JSON.stringify(body));
});

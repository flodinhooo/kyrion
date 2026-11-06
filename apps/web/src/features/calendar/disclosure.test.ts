import { beforeEach, describe, expect, it, vi } from "vitest";
import { disclosureSettings, sharedSources, disclosedEvents } from "./disclosure-model";
import { canEditCalendarEvent, canDeleteCalendarEvent } from "./calendar-model";
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.test", csrfIsValid: vi.fn(), requireApiSession: vi.fn() }));
import { csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { GET, PUT } from "@/app/api/calendar/personal-disclosure/route";
import { GET as sources } from "@/app/api/calendar/personal-disclosure/sources/route";
import { GET as events } from "@/app/api/calendar/personal-disclosure/sources/[id]/events/route";
const source = { id: "source-id", userId: "partner", username: "Partner", visibility: "AVAILABILITY" };
describe("personal calendar disclosure", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(requireApiSession).mockResolvedValue({ token: "server-only", user: { id: "member", username: "Member" } });
    vi.mocked(csrfIsValid).mockResolvedValue(true);
  });
  it("rejects malformed or private shared sources and invalid settings", () => {
    expect(sharedSources([{ ...source, visibility: "PRIVATE" }])).toBeNull();
    expect(disclosureSettings([{ id: "id", calendarId: "calendar", visibility: "DETAILS", revision: "1" }])).toBeNull();
    expect(disclosureSettings([{ id: "id", calendarId: "calendar", visibility: "PRIVATE", revision: 1 }])).toHaveLength(1);
  });
  it("preserves availability redaction even if an unexpected upstream title is present", () => {
    const parsed = disclosedEvents({ source, items: [{ id: "opaque", title: "secret", description: "secret", startsAt: "2026-11-10", endsAt: "2026-11-11", etag: "secret" }] }, source.id, "Belegt")!;
    expect(parsed[0]).toMatchObject({ title: "Belegt", description: null, allDay: true, canEdit: false, canDelete: false });
    expect(JSON.stringify(parsed)).not.toContain("secret");
    expect(canEditCalendarEvent(parsed[0], true)).toBe(false);
    expect(canDeleteCalendarEvent(parsed[0], true)).toBe(false);
  });
  it("rejects mismatched source identity and invalid event dates", () => {
    expect(disclosedEvents({ source, items: [] }, "foreign", "Busy")).toBeNull();
    expect(disclosedEvents({ source, items: [{ id: "opaque", startsAt: "bad", endsAt: "bad" }] }, source.id, "Busy")).toBeNull();
  });
  it("requires authentication on settings sources and events before any Core call", async () => {
    vi.mocked(requireApiSession).mockResolvedValue(Response.json({ code: "UNAUTHENTICATED" }, { status: 401 }));
    const upstream = vi.spyOn(globalThis, "fetch");
    expect((await GET()).status).toBe(401);
    expect((await sources()).status).toBe(401);
    expect((await events(new Request("http://web.test"), { params: Promise.resolve({ id: "source" }) })).status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });
  it("requires CSRF to change disclosure", async () => {
    vi.mocked(csrfIsValid).mockResolvedValue(false);
    const upstream = vi.spyOn(globalThis, "fetch");
    expect((await PUT(new Request("http://web.test", { method: "PUT", body: "{}" }))).status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
  });
  it("forwards only bounded read parameters with server credentials and no cache", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ source, items: [] }));
    const response = await events(new Request("http://web.test?start=2026-11-01T00:00:00Z&end=2026-12-01T00:00:00Z&userId=forged&calendarId=secret"), { params: Promise.resolve({ id: "source" }) });
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(upstream).toHaveBeenCalledWith("http://core.test/v1/calendar/personal-disclosure/sources/source/events?start=2026-11-01T00%3A00%3A00Z&end=2026-12-01T00%3A00%3A00Z", expect.objectContaining({ cache: "no-store", headers: { Authorization: "Bearer server-only" } }));
  });
  it("preserves revision conflicts without replacing them with success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ code: "CALENDAR_DISCLOSURE_CONFLICT" }, { status: 409 }));
    const response = await PUT(new Request("http://web.test", { method: "PUT", body: JSON.stringify({ calendarId: "calendar", visibility: "PRIVATE", revision: 1 }) }));
    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({ code: "CALENDAR_DISCLOSURE_CONFLICT" });
  });
});

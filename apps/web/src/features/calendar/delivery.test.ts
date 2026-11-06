import { beforeEach, describe, expect, it, vi } from "vitest";
import { destinationSetting, deliveryView, householdEditorIsDirty } from "./delivery-model";
import { editorForEvent, type CalendarEvent } from "./calendar-model";
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.test", csrfIsValid: vi.fn(), requireApiSession: vi.fn() }));
import { csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { GET, PUT } from "@/app/api/calendar/household-destination/route";
import { GET as status, POST } from "@/app/api/calendar/household-events/[id]/deliveries/route";
import { DELETE } from "@/app/api/calendar/household-events/[id]/route";
const id = "8d32bc75-bdf0-4f81-9bdb-b287cff71264";
const context = () => ({ params: Promise.resolve({ id }) });
const request = (method: string, body?: unknown) => new Request("http://web.test", { method, ...(body ? { body: JSON.stringify(body) } : {}) });
describe("household calendar delivery", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(requireApiSession).mockResolvedValue({ token: "server-only", user: { id: "member", username: "Member" } });
    vi.mocked(csrfIsValid).mockResolvedValue(true);
  });
  it("rejects malformed settings and negative or fractional revisions", () => {
    expect(destinationSetting({ id: null, calendarId: null, enabled: false, revision: 0 })).not.toBeNull();
    expect(destinationSetting({ id: null, calendarId: null, enabled: "false", revision: 0 })).toBeNull();
    expect(deliveryView({ revision: -1, targets: [], items: [] })).toBeNull();
    expect(deliveryView({ revision: 0.5, targets: [], items: [] })).toBeNull();
  });
  it("retains partial result states and reconstructs only public delivery fields", () => {
    const value = deliveryView({ revision: 2, targets: [{ userId: "partner", username: "Partner", targetId: null, calendarId: "secret" }],
      items: [{ id: "copy", userId: "partner", username: "Partner", state: "NEEDS_REVIEW", deliveredRevision: null, errorCode: "CALENDAR_DELIVERY_UNCERTAIN", etag: "secret" }] });
    expect(value?.items[0].state).toBe("NEEDS_REVIEW");
    expect(JSON.stringify(value)).not.toContain("secret");
    expect(deliveryView({ revision: 0, targets: [], items: [{ id: "id", userId: "partner", username: null, state: "invented-success", deliveredRevision: 0, errorCode: null }] })).toBeNull();
  });
  it("blocks sending unsaved edits including invalid form dates", () => {
    const event: CalendarEvent = { id: "household:event", title: "Dinner", description: null, startsAt: "2026-11-10T10:00:00Z", endsAt: "2026-11-10T11:00:00Z", source: "household" };
    const editor = editorForEvent(event);
    expect(householdEditorIsDirty(editor, event)).toBe(false);
    expect(householdEditorIsDirty({ ...editor, title: "Changed" }, event)).toBe(true);
    expect(householdEditorIsDirty({ ...editor, startsAt: "" }, event)).toBe(true);
  });
  it("requires authentication for personal settings and event delivery", async () => {
    vi.mocked(requireApiSession).mockResolvedValue(Response.json({ code: "UNAUTHENTICATED" }, { status: 401 }));
    const upstream = vi.spyOn(globalThis, "fetch");
    expect((await GET()).status).toBe(401);
    expect((await status(request("GET"), context())).status).toBe(401);
    expect((await POST(request("POST", {}), context())).status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });
  it("requires CSRF for opt in and every explicit delivery request", async () => {
    vi.mocked(csrfIsValid).mockResolvedValue(false);
    const upstream = vi.spyOn(globalThis, "fetch");
    expect((await PUT(request("PUT", {}))).status).toBe(403);
    expect((await POST(request("POST", {}), context())).status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
  });
  it("forwards one opaque target and saved revision with server credentials without cache", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ state: "NEEDS_REVIEW" }));
    const body = { targetId: "opaque-grant", revision: 2 };
    const response = await POST(request("POST", body), context());
    expect(await response.json()).toEqual({ state: "NEEDS_REVIEW" });
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(upstream).toHaveBeenCalledWith(`http://core.test/v1/calendar/household-events/${id}/deliveries`, expect.objectContaining({
      method: "POST", body: JSON.stringify(body), headers: { Authorization: "Bearer server-only", "Content-Type": "application/json" }, cache: "no-store" }));
  });
  it("preserves stale revisions and explicit external-copy retention on deletion", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({ code: "CALENDAR_DELIVERY_STALE" }, { status: 409 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    expect((await POST(request("POST", { targetId: "grant", revision: 1 }), context())).status).toBe(409);
    expect((await DELETE(new Request(`http://web.test?revision=2&retainExternalCopies=true` , { method: "DELETE" }), context())).status).toBe(204);
    expect(upstream.mock.calls[1][0]).toBe(`http://core.test/v1/calendar/household-events/${id}?revision=2&retainExternalCopies=true`);
  });
});

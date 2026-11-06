import { beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.test", csrfIsValid: vi.fn(), requireApiSession: vi.fn() }));
import { csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { POST } from "@/app/api/calendar/household-events/route";
import { PUT, DELETE } from "@/app/api/calendar/household-events/[id]/route";
import { GET as members } from "@/app/api/calendar/household-events/members/route";
import { GET as combined } from "@/app/api/calendar/events/route";

const id = "8d32bc75-bdf0-4f81-9bdb-b287cff71264";
const context = () => ({ params: Promise.resolve({ id }) });
const request = (method: string, body?: unknown) => new Request(`http://web.test/api/calendar/household-events/${id}?revision=4`, {
  method, ...(body ? { body: JSON.stringify(body), headers: { "Content-Type": "application/json" } } : {}),
});

describe("household event server routes", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(requireApiSession).mockResolvedValue({ token: "server-only", user: { id: "member", username: "Member" } });
    vi.mocked(csrfIsValid).mockResolvedValue(true);
  });

  it("requires authentication for every mutation and member read", async () => {
    vi.mocked(requireApiSession).mockResolvedValue(Response.json({ code: "UNAUTHENTICATED" }, { status: 401 }));
    const upstream = vi.spyOn(globalThis, "fetch");
    expect((await POST(request("POST", {}))).status).toBe(401);
    expect((await PUT(request("PUT", {}), context())).status).toBe(401);
    expect((await DELETE(request("DELETE"), context())).status).toBe(401);
    expect((await members()).status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("blocks all writes without CSRF before contacting Core", async () => {
    vi.mocked(csrfIsValid).mockResolvedValue(false);
    const upstream = vi.spyOn(globalThis, "fetch");
    expect((await POST(request("POST", {}))).status).toBe(403);
    expect((await PUT(request("PUT", {}), context())).status).toBe(403);
    expect((await DELETE(request("DELETE"), context())).status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("uses only the server session to forward creation and preserves participant payload and 201", async () => {
    const payload = { title: "Dinner", participantIds: ["partner"] };
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ id }, { status: 201 }));
    const response = await POST(request("POST", payload));
    expect(response.status).toBe(201);
    expect(upstream).toHaveBeenCalledWith("http://core.test/v1/calendar/household-events", expect.objectContaining({
      method: "POST", headers: { Authorization: "Bearer server-only", "Content-Type": "application/json" },
      body: JSON.stringify(payload), cache: "no-store",
    }));
  });

  it("keeps revision conflicts distinct and forwards deletion revision without parsing an empty success", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({ code: "HOUSEHOLD_CALENDAR_CONFLICT" }, { status: 409 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const conflict = await PUT(request("PUT", { revision: 4 }), context());
    expect(conflict.status).toBe(409);
    expect(await conflict.json()).toEqual({ code: "HOUSEHOLD_CALENDAR_CONFLICT" });
    expect((await DELETE(request("DELETE"), context())).status).toBe(204);
    expect(upstream.mock.calls[1][0]).toBe(`http://core.test/v1/calendar/household-events/${id}?revision=4`);
  });

  it("does not cache participant names and preserves Core denials", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ code: "FORBIDDEN" }, { status: 403 }));
    const response = await members();
    expect(response.status).toBe(403);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(upstream).toHaveBeenCalledWith("http://core.test/v1/calendar/household-events/members", expect.objectContaining({
      cache: "no-store", headers: { Authorization: "Bearer server-only" },
    }));
  });

  it("combines canonical household events without collisions and bounds their read to the selected range", async () => {
    const event = { id, title: "Dinner", startsAt: "2026-11-10T10:00:00Z", endsAt: "2026-11-10T11:00:00Z",
      participantIds: ["creator", "partner"], createdBy: "creator", canEdit: true, canDelete: false, revision: 4 };
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json([{ ...event, id }]))
      .mockResolvedValueOnce(Response.json({ items: [] })).mockResolvedValueOnce(Response.json([event]));
    const query = new URLSearchParams({ start: "2026-11-01T00:00:00Z", end: "2026-12-01T00:00:00Z" });
    const response = await combined(new Request(`http://web.test/api/calendar/events?${query}`));
    expect(await response.json()).toMatchObject({ items: [expect.objectContaining({ id, source: "local" }),
      expect.objectContaining({ id: `household:${id}`, source: "household", canDelete: false })], household: { status: "ready" } });
    expect(upstream.mock.calls[2][0]).toBe(`http://core.test/v1/calendar/household-events?${query}`);
  });

  it("reports missing household support without hiding existing calendar data", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json([{ id, title: "Legacy", startsAt: "2026-11-10T10:00:00Z", endsAt: "2026-11-10T11:00:00Z" }]))
      .mockResolvedValueOnce(Response.json({ items: [] })).mockResolvedValueOnce(Response.json({ code: "NOT_FOUND" }, { status: 404 }));
    expect(await (await combined()).json()).toMatchObject({ items: [expect.objectContaining({ title: "Legacy" })], household: { status: "error" } });
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-auth", () => ({
  CORE_SERVICE_URL: "http://core.test",
  csrfIsValid: vi.fn(),
  requireApiSession: vi.fn(),
}));

import { csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { GET, POST } from "./route";

describe("GET /api/calendar/events", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("requires the Web session and forwards its token to Core", async () => {
    vi.mocked(requireApiSession).mockResolvedValue({
      token: "server-only-token",
      user: { id: "owner", username: "Owner" },
    });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([{ id: "local-1", title: "Local", startsAt: "2026-09-17T09:00:00Z", endsAt: "2026-09-17T10:00:00Z" }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: "same-id", summary: "Google", start: "2026-09-18T09:00:00Z", end: "2026-09-18T10:00:00Z" }] }), { status: 200 }));

    const response = await GET();

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://core.test/v1/calendar/events",
      expect.objectContaining({ headers: { Authorization: "Bearer server-only-token" } }),
    );
    expect(await response.json()).toMatchObject({ items: [
      expect.objectContaining({ id: "local-1", source: "local" }),
      expect.objectContaining({ id: "google:same-id", source: "google" }),
    ] });
    expect(fetchMock).toHaveBeenCalledWith("http://core.test/v1/integrations/google/calendar/events", expect.anything());
  });

  it("keeps local events when Google is unavailable", async () => {
    vi.mocked(requireApiSession).mockResolvedValue({ token: "server-only-token", user: { id: "owner", username: "Owner" } });
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([{ id: "local-1", title: "Local", startsAt: "2026-09-17T09:00:00Z", endsAt: "2026-09-17T10:00:00Z" }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ code: "GOOGLE_UNAVAILABLE" }), { status: 503 }));
    const response = await GET();
    expect(response.status).toBe(200);
    expect((await response.json()).items).toHaveLength(1);
  });

  it("returns Google events when the local calendar is empty", async () => {
    vi.mocked(requireApiSession).mockResolvedValue({ token: "server-only-token", user: { id: "owner", username: "Owner" } });
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: "google-1", summary: "Remote", start: "2026-09-17T09:00:00Z", end: "2026-09-17T10:00:00Z" }] }), { status: 200 }));
    const response = await GET();
    expect((await response.json()).items).toEqual([expect.objectContaining({ id: "google:google-1", source: "google" })]);
  });

  it("keeps local events when the optional Google request rejects", async () => {
    vi.mocked(requireApiSession).mockResolvedValue({ token: "server-only-token", user: { id: "owner", username: "Owner" } });
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json([{ id: "local-1", title: "Local", startsAt: "2026-09-17T09:00:00Z", endsAt: "2026-09-17T10:00:00Z" }]))
      .mockRejectedValueOnce(new Error("network unavailable"));
    const response = await GET();
    expect(response.status).toBe(200);
    expect((await response.json()).items).toHaveLength(1);
  });

  it("forwards the selected range and calendar and excludes linked duplicate events", async () => {
    vi.mocked(requireApiSession).mockResolvedValue({ token: "token", user: { id: "owner", username: "Owner" } });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json([{ id: "local", title: "Linked", startsAt: "2026-09-17T09:00:00Z", endsAt: "2026-09-17T10:00:00Z", googleCalendarId: "selected", googleEventId: "remote" }]))
      .mockResolvedValueOnce(Response.json({ items: [{ id: "remote", summary: "Linked", start: "2026-09-17T09:00:00Z", end: "2026-09-17T10:00:00Z" }] }));
    const query = new URLSearchParams({ calendarId: "selected", start: "2026-09-01T00:00:00Z", end: "2026-10-01T00:00:00Z" });
    const response = await GET(new Request(`http://web.test/api/calendar/events?${query}`));
    expect((await response.json()).items).toHaveLength(1);
    expect(fetchMock.mock.calls[1][0]).toBe(`http://core.test/v1/integrations/google/calendar/events?${query}`);
  });

  it("distinguishes a provider error from an empty connected calendar", async () => {
    vi.mocked(requireApiSession).mockResolvedValue({ token: "token", user: { id: "owner", username: "Owner" } });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json([]))
      .mockResolvedValueOnce(Response.json({ code: "GOOGLE_REAUTHORIZATION_REQUIRED" }, { status: 409 }));
    expect(await (await GET()).json()).toMatchObject({ items: [], google: { status: "error", code: "GOOGLE_REAUTHORIZATION_REQUIRED" } });
  });

  it("rejects malformed local responses instead of reporting an empty calendar", async () => {
    vi.mocked(requireApiSession).mockResolvedValue({ token: "token", user: { id: "owner", username: "Owner" } });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({ unexpected: [] })).mockResolvedValueOnce(Response.json({ items: [] }));
    expect((await GET()).status).toBe(502);
  });

  it("returns 401 without calling Core when the session is missing", async () => {
    vi.mocked(requireApiSession).mockResolvedValue(
      Response.json({ code: "UNAUTHENTICATED" }, { status: 401 }),
    );
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await GET();

    expect(response.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("POST /api/calendar/events", () => {
  const event = { title: "Local appointment", description: null, startsAt: "2026-10-12T09:00:00Z", endsAt: "2026-10-12T10:00:00Z", timeZone: "Europe/Zurich", syncToGoogle: false };
  const request = () => new Request("http://web.test/api/calendar/events", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-kyrion-csrf": "test-csrf" },
    body: JSON.stringify(event),
  });

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(requireApiSession).mockResolvedValue({ token: "server-only-token", user: { id: "owner", username: "Owner" } });
    vi.mocked(csrfIsValid).mockResolvedValue(true);
  });

  it("forwards authenticated creation and returns the persisted Core event", async () => {
    const persisted = { id: "local-created", ...event };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(persisted), { status: 200 }));
    const response = await POST(request());
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith("http://core.test/v1/calendar/events", {
      method: "POST",
      headers: { Authorization: "Bearer server-only-token", "Content-Type": "application/json" },
      body: JSON.stringify(event),
    });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(persisted);
  });

  it("rejects creation without a session before contacting Core", async () => {
    vi.mocked(requireApiSession).mockResolvedValue(Response.json({ code: "UNAUTHENTICATED" }, { status: 401 }));
    const fetchMock = vi.spyOn(globalThis, "fetch");
    expect((await POST(request())).status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects invalid CSRF before contacting Core", async () => {
    vi.mocked(csrfIsValid).mockResolvedValue(false);
    const fetchMock = vi.spyOn(globalThis, "fetch");
    const response = await POST(request());
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ code: "CSRF_INVALID" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves a Core permission rejection", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ code: "FORBIDDEN" }, { status: 403 }));
    const response = await POST(request());
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ code: "FORBIDDEN" });
  });

  it("reports Core unavailability without a successful creation", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    const response = await POST(request());
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ code: "CORE_UNAVAILABLE" });
  });
});

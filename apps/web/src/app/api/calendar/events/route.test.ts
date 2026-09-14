import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-auth", () => ({
  CORE_SERVICE_URL: "http://core.test",
  csrfIsValid: vi.fn(),
  requireApiSession: vi.fn(),
}));

import { requireApiSession } from "@/lib/server-auth";
import { GET } from "./route";

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
    expect(await response.json()).toEqual({ items: [
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

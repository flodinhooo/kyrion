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
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );

    const response = await GET();

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://core.test/v1/calendar/events",
      expect.objectContaining({ headers: { Authorization: "Bearer server-only-token" } }),
    );
    expect(await response.text()).not.toContain("server-only-token");
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

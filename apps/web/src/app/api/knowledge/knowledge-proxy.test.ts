import {beforeEach, describe, expect, it, vi} from "vitest";

const mocks = vi.hoisted(() => ({session: vi.fn(), csrf: vi.fn()}));
vi.mock("@/lib/server-auth", () => ({CORE_SERVICE_URL: "http://core.test",
  requireApiSession: mocks.session, csrfIsValid: mocks.csrf}));
import {GET, POST} from "./[...path]/route";

describe("knowledge session and CSRF proxy", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mocks.session.mockResolvedValue({token: "server-only-token", user: {id: "a", username: "a"}});
    mocks.csrf.mockResolvedValue(true);
  });
  it("rejects unauthenticated access and mutation without CSRF", async () => {
    const fetch = vi.spyOn(globalThis, "fetch");
    mocks.session.mockResolvedValueOnce(Response.json({code: "UNAUTHENTICATED"}, {status: 401}));
    expect((await GET(new Request("http://web/api/knowledge/spaces"), {params: Promise.resolve({path: ["spaces"]})})).status).toBe(401);
    mocks.csrf.mockResolvedValueOnce(false);
    expect((await POST(new Request("http://web/api/knowledge/spaces", {method: "POST"}), {params: Promise.resolve({path: ["spaces"]})})).status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("never forwards arbitrary paths or browser authorization", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json([]));
    expect((await GET(new Request("http://web/api/knowledge/spaces"), {params: Promise.resolve({path: ["..", "rbac"]})})).status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
    const response = await GET(new Request("http://web/api/knowledge/spaces", {headers: {Authorization: "Bearer forged"}}),
      {params: Promise.resolve({path: ["spaces"]})});
    expect(response.headers.get("cache-control")).toBe("no-store");
    const init = fetch.mock.calls[0][1];
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer server-only-token");
  });
});

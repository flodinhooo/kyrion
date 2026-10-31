import { beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("@/features/spaces/proxy", () => ({ spaceProxy: vi.fn() }));
import { spaceProxy } from "@/features/spaces/proxy";
import { GET, POST, PUT } from "./[...path]/route";

describe("identity route allowlist", () => {
  beforeEach(() => vi.resetAllMocks());
  it.each(["recovery", "business/unknown", "../auth/setup"])("never proxies %s", async (path) => {
    const result = await POST(new Request("http://local/api/identity", { method: "POST" }), { params: Promise.resolve({ path: path.split("/") }) });
    expect(result.status).toBe(404); expect(spaceProxy).not.toHaveBeenCalled();
  });
  it("rejects unsupported mutations", async () => {
    expect((await PUT(new Request("http://local/api/identity/email", { method: "PUT" }), { params: Promise.resolve({ path: ["email"] }) })).status).toBe(404);
  });
  it("forwards the current user's email endpoint through the CSRF/session proxy", async () => {
    vi.mocked(spaceProxy).mockResolvedValue(Response.json({ status: "PENDING" }));
    await GET(new Request("http://local/api/identity/email"), { params: Promise.resolve({ path: ["email"] }) });
    expect(spaceProxy).toHaveBeenCalledWith(expect.any(Request), "/v1/identity/email");
  });
});

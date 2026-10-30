import {afterEach, describe, expect, it, vi} from "vitest";
import {POST} from "./route";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
const key = "a".repeat(64);

function request(body: unknown, origin = "http://localhost:3000", host = "http://localhost:3000") {
  return new Request(`${host}/api/dev-recovery`, {
    method: "POST",
    headers: {origin, "Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
}

describe("local recovery proxy", () => {
  it("rejects production, remote hosts and cross-origin requests before fetching", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    vi.stubEnv("NODE_ENV", "production");
    expect((await POST(request({key, action: "start"}))).status).toBe(403);
    vi.stubEnv("NODE_ENV", "development");
    expect((await POST(request({key, action: "start"}, "http://evil.test"))).status).toBe(403);
    expect((await POST(request({key, action: "start"}, "http://node:3000", "http://node:3000"))).status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("rejects executable input, invalid keys and oversized requests", async () => {
    vi.stubEnv("NODE_ENV", "development");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    for (const body of [{key, action: "stop"}, {key, action: ["start"]}, {key: "bad", action: "start"}, {
      key,
      action: "start",
      command: "whoami"
    }]) {
      expect((await POST(request(body))).status).toBe(400);
    }
    expect((await POST(request({key: "a".repeat(600), action: "start"}))).status).toBe(413);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("sends status requests to the fixed helper without exposing the key in the URL", async () => {
    vi.stubEnv("NODE_ENV", "development");
    const fetch = vi.fn().mockResolvedValue(Response.json({state: "idle", results: [], correlationId: null}));
    vi.stubGlobal("fetch", fetch);
    expect((await POST(request({key, action: "status"}))).status).toBe(200);
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:17654/", expect.objectContaining({
      method: "GET",
      headers: expect.objectContaining({Authorization: `Bearer ${key}`})
    }));
  });
  it("reports unavailable helper without leaking internal errors", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private detail")));
    const response = await POST(request({key, action: "start"}));
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({code: "RECOVERY_HELPER_UNAVAILABLE"});
  });
});

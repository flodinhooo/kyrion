import {beforeEach, expect, it, vi} from "vitest";
import {randomBytes} from "node:crypto";

vi.mock("next/headers", () => ({cookies: vi.fn(async () => ({set: vi.fn()}))}));
vi.mock("@/lib/server-auth", () => ({
  CORE_SERVICE_URL: "http://core.test",
  CSRF_COOKIE: "csrf",
  SESSION_COOKIE: "session",
  secureCookie: () => true
}));

import {authenticate} from "./session-cookie";

beforeEach(() => vi.restoreAllMocks());

it("forwards the transient bootstrap secret in a header and never returns it", async () => {
  const setupSecret = randomBytes(32).toString("base64url");
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({
    user: {id: "owner"}, sessionToken: "server-session", expiresAt: "2026-11-01T00:00:00Z",
  }));
  const response = await authenticate(new Request("https://web.test/api/auth/setup", {
    method: "POST", body: JSON.stringify({username: "owner", password: "test-password", setupSecret}),
  }), "/v1/auth/setup", 201);
  expect(fetchMock).toHaveBeenCalledWith("http://core.test/v1/auth/setup", expect.objectContaining({
    headers: {"Content-Type": "application/json", "X-Kyrion-Setup-Secret": setupSecret},
    body: JSON.stringify({username: "owner", password: "test-password"}),
  }));
  expect(response.status).toBe(201);
  expect(await response.json()).toEqual({user: {id: "owner"}});
});

it("fails closed without a bootstrap secret before calling Core", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  const response = await authenticate(new Request("https://web.test/api/auth/setup", {
    method: "POST", body: JSON.stringify({username: "owner", password: "test-password"}),
  }), "/v1/auth/setup", 201);
  expect(response.status).toBe(403);
  expect(fetchMock).not.toHaveBeenCalled();
});

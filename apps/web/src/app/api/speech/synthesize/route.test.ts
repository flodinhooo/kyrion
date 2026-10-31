import { beforeEach, expect, it, vi } from "vitest";
vi.mock("@/lib/server-auth", () => ({ csrfIsValid: vi.fn(), requireApiSession: vi.fn() }));
import { csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { POST } from "./route";

beforeEach(() => { vi.resetAllMocks(); vi.stubGlobal("fetch", vi.fn()); });
it("requires CSRF before any provider call", async () => {
  vi.mocked(csrfIsValid).mockResolvedValue(false);
  expect((await POST(new Request("http://local/api/speech/synthesize", { method: "POST" }))).status).toBe(403);
  expect(fetch).not.toHaveBeenCalled();
});
it("blocks Business synthesis before text reaches the AI service", async () => {
  vi.mocked(csrfIsValid).mockResolvedValue(true);
  vi.mocked(requireApiSession).mockResolvedValue({ token: "session", user: { id: "user", username: "user", permissions: ["conversations:read"], space: { id: "space", name: "Business", type: "BUSINESS", status: "ACTIVE", defaultRoleKey: "USER" } } });
  expect((await POST(new Request("http://local/api/speech/synthesize", { method: "POST", body: JSON.stringify({ text: "Private business content" }) }))).status).toBe(403);
  expect(fetch).not.toHaveBeenCalled();
});
it("keeps authorized HOME synthesis available", async () => {
  vi.mocked(csrfIsValid).mockResolvedValue(true);
  vi.mocked(requireApiSession).mockResolvedValue({ token: "session", user: { id: "user", username: "user", permissions: ["conversations:read"], space: { id: "space", name: "Home", type: "HOME", status: "ACTIVE", defaultRoleKey: "USER" } } });
  vi.mocked(fetch).mockResolvedValue(new Response(new Uint8Array([1, 2, 3])));
  const result = await POST(new Request("http://local/api/speech/synthesize", { method: "POST", body: JSON.stringify({ text: "Home response", voiceId: "velora", locale: "en" }) }));
  expect(result.status).toBe(200); expect(fetch).toHaveBeenCalledOnce();
});

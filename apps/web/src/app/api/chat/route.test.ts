import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

vi.mock("@/lib/server-auth", () => ({
  CORE_SERVICE_URL: "http://core.test",
  requireApiSession: vi.fn(async () => ({token: "synthetic-session"})),
  csrfIsValid: vi.fn(async () => true),
}));
import {POST} from "./route";
import {csrfIsValid, requireApiSession} from "@/lib/server-auth";

const conversationId = "11111111-1111-4111-8111-111111111111";
const turnId = "22222222-2222-4222-8222-222222222222";
const model = (cloud: boolean) => ({
  id: cloud ? "cloud-profile" : "local", label: "Operator model",
  provider: cloud ? "gemini" : "ollama", local: !cloud, enabled: true, available: true,
  sizeBytes: 0, parameterSize: "unknown", quantization: "unknown", capabilities: ["chat", "streaming"]
});
const body = (cloud: boolean, consent = cloud) => ({
  conversationId,
  title: "Synthetic test",
  modelId: cloud ? "cloud-profile" : "local",
  locale: "en",
  cloudConsent: consent,
  message: {id: turnId, content: "Current prompt", createdAt: "2026-10-30T12:00:00Z"}
});

describe("multi-provider chat disclosure boundary (simulated upstreams)", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  function upstream(cloud: boolean, privateContext = false) {
    const fetcher = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.endsWith("/v1/models")) return Response.json({
        defaultModelId: "local",
        models: [model(false), model(true)]
      });
      if (input.endsWith("/v1/ai/route")) return Response.json({
        model: model(cloud),
        reason: "explicit_profile",
        alternatives: [],
        rejected: {}
      });
      if (input.endsWith("/actions/interpret")) return Response.json({kind: "none"});
      if (input.endsWith("/turns/complete")) return Response.json({});
      if (input.endsWith("/turns")) return Response.json({
        conversationId, turnId, estimatedTokens: 10,
        tokenBudget: 3072, compacted: false,
        messages: privateContext ? [{role: "assistant", content: "PRIVATE HISTORY"}, {
          role: "user",
          content: "Current prompt"
        }] : [{role: "user", content: "Current prompt"}],
        usedMemories: privateContext ? [{
          id: "memory",
          category: "other",
          content: "PRIVATE MEMORY",
          sensitivity: "sensitive"
        }] : [],
      });
      if (input.endsWith("/chat/stream")) {
        const value = JSON.parse(String(init?.body));
        expect(value.cloudConsent).toBe(cloud);
        return new Response([
          {
            type: "model.selected",
            provider: cloud ? "gemini" : "ollama",
            modelId: "operator-model",
            profileId: value.modelId
          },
          {type: "message.started", messageId: "assistant-id"},
          {type: "message.delta", messageId: "assistant-id", delta: "Synthetic answer"},
          {type: "usage", usage: {inputTokens: 4, outputTokens: 2}},
          {type: "message.completed", messageId: "assistant-id"},
        ].map(event => JSON.stringify(event)).join("\n") + "\n");
      }
      throw new Error(`Unexpected simulated URL ${input}`);
    });
    vi.stubGlobal("fetch", fetcher);
    return fetcher;
  }

  it("exports only Core-approved current prompt and persists ordinary stream plus usage", async () => {
    const fetcher = upstream(true);
    const response = await POST(new Request("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify(body(true))
    }));
    expect(response.status).toBe(200);
    expect(await response.text()).toContain('"type":"usage"');
    const contextCall = fetcher.mock.calls.find(([url]) => url.endsWith("/turns"));
    expect(JSON.parse(String(contextCall?.[1]?.body))).toMatchObject({
      externalProvider: "gemini",
      externalConsent: "current_message"
    });
    const chatCall = fetcher.mock.calls.find(([url]) => url.endsWith("/chat/stream"));
    expect(JSON.parse(String(chatCall?.[1]?.body))).toMatchObject({turnId});
    expect(String(chatCall?.[1]?.body)).not.toContain("memoryContext");
    expect(fetcher.mock.calls.some(([url]) => url.endsWith("/turns/complete"))).toBe(true);
  });

  it("refuses cloud without explicit consent before starting a Core turn", async () => {
    const fetcher = upstream(true);
    const response = await POST(new Request("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify(body(true, false))
    }));
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({code: "CLOUD_NOT_ALLOWED"});
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("fails closed if an older Core returns history or personal memories", async () => {
    const fetcher = upstream(true, true);
    const response = await POST(new Request("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify(body(true))
    }));
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({code: "CONTEXT_NOT_ALLOWED"});
    expect(fetcher.mock.calls.some(([url]) => url.endsWith("/chat/stream"))).toBe(false);
  });

  it("preserves local history and confirmed-memory context", async () => {
    const fetcher = upstream(false, true);
    const response = await POST(new Request("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify(body(false))
    }));
    await response.text();
    expect(response.status).toBe(200);
    const chatCall = fetcher.mock.calls.find(([url]) => url.endsWith("/chat/stream"));
    expect(String(chatCall?.[1]?.body)).not.toContain("PRIVATE MEMORY");
    expect(String(chatCall?.[1]?.body)).not.toContain("messages");
    const coreCall = fetcher.mock.calls.find(([url]) => url.endsWith("/turns"));
    expect(String(coreCall?.[1]?.body)).not.toContain("externalProvider");
  });

  it("keeps session and CSRF checks ahead of provider access", async () => {
    const fetcher = upstream(true);
    vi.mocked(requireApiSession).mockResolvedValueOnce(new Response(null, {status: 401}) as never);
    expect((await POST(new Request("http://localhost/api/chat", {method: "POST"}))).status).toBe(401);
    vi.mocked(csrfIsValid).mockResolvedValueOnce(false);
    expect((await POST(new Request("http://localhost/api/chat", {method: "POST"}))).status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });
});

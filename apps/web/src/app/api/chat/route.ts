import type { ChatRequest } from "@/features/chat/contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000";
const CONTEXT_TOKEN_BUDGET = 3072;

type CoreContext = {
  conversationId: string;
  turnId: string;
  messages: Array<{ role: "user" | "assistant"; content: string }>;
  estimatedTokens: number;
  tokenBudget: number;
  compacted: boolean;
  usedMemories: Array<{ id: string; category: string; content: string; sensitivity: "standard" | "sensitive" }>;
};

function isCoreContext(value: unknown): value is CoreContext {
  if (!value || typeof value !== "object") return false;
  const context = value as Partial<CoreContext>;
  return typeof context.conversationId === "string"
    && typeof context.turnId === "string"
    && Array.isArray(context.messages)
    && context.messages.length > 0
    && context.messages.every((message) =>
      !!message
      && (message.role === "user" || message.role === "assistant")
      && typeof message.content === "string",
    )
    && typeof context.estimatedTokens === "number"
    && typeof context.tokenBudget === "number"
    && typeof context.compacted === "boolean"
    && Array.isArray(context.usedMemories)
    && context.usedMemories.length <= 3
    && context.usedMemories.every((memory) =>
      !!memory && typeof memory.id === "string" && typeof memory.category === "string"
      && typeof memory.content === "string"
      && (memory.sensitivity === "standard" || memory.sensitivity === "sensitive"),
    );
}

function isChatRequest(value: unknown): value is ChatRequest {
  if (!value || typeof value !== "object") return false;
  const request = value as Partial<ChatRequest>;
  const message = request.message as Partial<ChatRequest["message"]> | undefined;
  return (request.locale === "de" || request.locale === "en")
    && typeof request.conversationId === "string"
    && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(request.conversationId)
    && typeof request.title === "string"
    && request.title.trim().length > 0
    && request.title.length <= 160
    && (request.modelId === undefined
      || (typeof request.modelId === "string"
        && request.modelId.trim().length > 0
        && request.modelId.length <= 128))
    && !!message
    && typeof message.id === "string"
    && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(message.id)
    && typeof message.content === "string"
    && message.content.trim().length > 0
    && message.content.length <= 100_000
    && typeof message.createdAt === "string"
    && !Number.isNaN(Date.parse(message.createdAt));
}

export async function POST(incomingRequest: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(incomingRequest))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  let body: unknown;
  let startedTurn: { conversationId: string; turnId: string; token: string } | null = null;
  try {
    body = await incomingRequest.json();
  } catch {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }

  if (!isChatRequest(body)) {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }

  try {
    const contextResponse = await fetch(`${CORE_SERVICE_URL}/v1/conversations/${body.conversationId}/turns`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({
        title: body.title,
        tokenBudget: CONTEXT_TOKEN_BUDGET,
        message: { ...body.message, role: "user" },
      }),
      cache: "no-store",
      signal: incomingRequest.signal,
    });
    if (!contextResponse.ok) {
      const code = contextResponse.status === 404
        ? "CONVERSATION_NOT_FOUND"
        : contextResponse.status === 409 ? "CONVERSATION_CONFLICT" : "INVALID_REQUEST";
      return Response.json({ code }, { status: contextResponse.status });
    }
    const contextValue: unknown = await contextResponse.json();
    if (!isCoreContext(contextValue)) {
      return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 502 });
    }
    startedTurn = { conversationId: body.conversationId, turnId: contextValue.turnId, token: auth.token };

    const response = await fetch(`${AI_SERVICE_URL}/v1/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversationId: body.conversationId,
        modelId: body.modelId,
        locale: body.locale,
        messages: contextValue.messages,
        memoryContext: contextValue.usedMemories,
      }),
      cache: "no-store",
      signal: incomingRequest.signal,
    });

    if (response.status === 400) {
      await failTurn(startedTurn, "INVALID_REQUEST");
      return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
    }

    if (!response.ok || !response.body) {
      await failTurn(startedTurn, "MODEL_UNAVAILABLE");
      return Response.json({ code: "MODEL_UNAVAILABLE" }, { status: 503 });
    }

    const persistedStream = persistAssistantStream(
      response.body,
      body.conversationId,
      auth.token,
      contextValue.turnId,
      contextValue.usedMemories,
      contextValue.compacted ? {
        estimatedTokens: contextValue.estimatedTokens,
        tokenBudget: contextValue.tokenBudget,
      } : null,
    );
    return new Response(persistedStream, {
      status: 200,
      headers: {
        "Content-Type": "application/x-ndjson",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Kyrion-Context-Compacted": String(contextValue.compacted),
        "X-Kyrion-Context-Tokens": String(contextValue.estimatedTokens),
        "X-Kyrion-Context-Budget": String(contextValue.tokenBudget),
      },
    });
  } catch {
    if (startedTurn) await failTurn(startedTurn, incomingRequest.signal.aborted ? "REQUEST_ABORTED" : "STREAM_FAILED");
    return Response.json({ code: "MODEL_UNAVAILABLE" }, { status: 503 });
  }
}

function persistAssistantStream(
  source: ReadableStream<Uint8Array>,
  conversationId: string,
  token: string,
  turnId: string,
  usedMemories: CoreContext["usedMemories"],
  compaction: { estimatedTokens: number; tokenBudget: number } | null,
) {
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();
  let buffer = "";
  let messageId: string | null = null;
  let assistantContent = "";
  let finalized = false;
  const reader = source.getReader();

  async function forwardLine(line: string, controller: ReadableStreamDefaultController<Uint8Array>) {
    if (!line.trim()) return;
    let event: { type?: string; messageId?: string; delta?: string };
    try { event = JSON.parse(line) as typeof event; } catch { controller.enqueue(encoder.encode(`${line}\n`)); return; }
    if (event.type === "message.started" && event.messageId) messageId = event.messageId;
    if (event.type === "message.delta" && typeof event.delta === "string") assistantContent += event.delta;
    if (event.type === "message.completed") {
      const persisted = messageId && assistantContent.trim()
        ? await persistAssistant(conversationId, token, turnId, messageId, assistantContent, "completed")
        : false;
      finalized = persisted;
      controller.enqueue(encoder.encode(persisted
        ? `${line}\n`
        : `${JSON.stringify({ type: "error", code: "CORE_UNAVAILABLE" })}\n`));
      return;
    }
    controller.enqueue(encoder.encode(`${line}\n`));
  }

  async function finalizeInterrupted() {
    if (finalized) return;
    finalized = true;
    if (messageId && assistantContent.trim()) {
      await persistAssistant(conversationId, token, turnId, messageId, assistantContent, "stopped");
    } else {
      await failTurn({ conversationId, turnId, token }, "REQUEST_ABORTED");
    }
  }

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      if (usedMemories.length > 0) controller.enqueue(encoder.encode(`${JSON.stringify({
        type: "memory.used", items: usedMemories,
      })}\n`));
      if (compaction) controller.enqueue(encoder.encode(`${JSON.stringify({
        type: "context.compacted",
        ...compaction,
      })}\n`));
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) await forwardLine(line, controller);
        }
        buffer += decoder.decode();
        await forwardLine(buffer, controller);
        if (!finalized) await finalizeInterrupted();
        controller.close();
      } catch (error) {
        await finalizeInterrupted();
        controller.error(error);
      } finally {
        reader.releaseLock();
      }
    },
    async cancel(reason) {
      await reader.cancel(reason).catch(() => undefined);
      await finalizeInterrupted();
    },
  });
}

async function persistAssistant(
  conversationId: string,
  token: string,
  turnId: string,
  messageId: string,
  content: string,
  status: "completed" | "stopped",
) {
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/conversations/${conversationId}/turns/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        turnId,
        status,
        message: { id: messageId, role: "assistant", content, createdAt: new Date().toISOString() },
      }),
      cache: "no-store",
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function failTurn(
  turn: { conversationId: string; turnId: string; token: string },
  errorCode: string,
) {
  try {
    await fetch(`${CORE_SERVICE_URL}/v1/conversations/${turn.conversationId}/turns/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${turn.token}` },
      body: JSON.stringify({ turnId: turn.turnId, status: "failed", errorCode }),
      cache: "no-store",
    });
  } catch { /* Core availability is already represented by the caller's error. */ }
}

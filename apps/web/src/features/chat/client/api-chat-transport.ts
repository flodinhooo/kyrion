import type { ChatTransport, ChatStreamOptions } from "@/features/chat/client/chat-transport";
import type { ChatEvent, ChatRequest } from "@/features/chat/contracts";
import { csrfHeader } from "@/features/auth/csrf";
import {modelMessages} from "@/features/models/messages";
import {isKnowledgeSource} from "@/features/knowledge/contracts";

export function parseEvent(line: string): ChatEvent {
  if (line.length > 1_000_000) throw new Error("Invalid stream event");
  const value: unknown = JSON.parse(line);
  if (!value || typeof value !== "object" || !("type" in value)) throw new Error("Invalid stream event");
  if (value.type === "routing.fallback" && "profileId" in value && typeof value.profileId === "string"
    && "attempt" in value && typeof value.attempt === "number" && Number.isInteger(value.attempt) && value.attempt > 0) {
    return {type: "routing.fallback", profileId: value.profileId, attempt: value.attempt};
  }
  const hasMessageId = "messageId" in value && typeof value.messageId === "string" && value.messageId.length > 0;
  if (value.type === "knowledge.sources" && hasMessageId && "items" in value && Array.isArray(value.items)
    && value.items.length <= 3 && value.items.every(isKnowledgeSource)) {
    return {type: "knowledge.sources", messageId: String(value.messageId), items: value.items};
  }
  if (value.type === "message.started" && hasMessageId) return {type: value.type, messageId: String(value.messageId)};
  if (value.type === "message.completed" && hasMessageId) return {type: value.type, messageId: String(value.messageId)};
  if (value.type === "message.delta" && hasMessageId && "delta" in value && typeof value.delta === "string") {
    return {type: value.type, messageId: String(value.messageId), delta: value.delta};
  }
  if (value.type === "error" && "code" in value && typeof value.code === "string" && responseErrorCodes.has(value.code)) {
    return {type: "error", code: value.code as Extract<ChatEvent, { type: "error" }>["code"]};
  }
  if (value.type === "model.selected" && "provider" in value && typeof value.provider === "string"
    && "modelId" in value && typeof value.modelId === "string" && "profileId" in value && typeof value.profileId === "string") {
    return {type: "model.selected", provider: value.provider, modelId: value.modelId, profileId: value.profileId};
  }
  if (value.type === "usage" && "usage" in value && value.usage && typeof value.usage === "object") {
    const usage: { inputTokens?: number | null; outputTokens?: number | null; totalTokens?: number | null } = {};
    for (const key of ["inputTokens", "outputTokens", "totalTokens"] as const) {
      if (key in value.usage) {
        const count = Reflect.get(value.usage, key);
        if (count !== null && (typeof count !== "number" || !Number.isInteger(count) || count < 0)) throw new Error("Invalid usage");
        usage[key] = count;
      }
    }
    return {type: "usage", usage};
  }
  if (value.type === "context.compacted" && "estimatedTokens" in value && typeof value.estimatedTokens === "number"
    && "tokenBudget" in value && typeof value.tokenBudget === "number") {
    return {type: value.type, estimatedTokens: value.estimatedTokens, tokenBudget: value.tokenBudget};
  }
  if (value.type === "memory.used" && "items" in value && Array.isArray(value.items) && value.items.length <= 3) {
    const items = value.items.map<Extract<ChatEvent, { type: "memory.used" }>["items"][number]>((item: unknown) => {
      if (!item || typeof item !== "object" || !("id" in item) || typeof item.id !== "string"
        || !("category" in item) || typeof item.category !== "string" || !("content" in item) || typeof item.content !== "string"
        || !("sensitivity" in item) || (item.sensitivity !== "standard" && item.sensitivity !== "sensitive")) throw new Error("Invalid memory event");
      return {id: item.id, category: item.category, content: item.content, sensitivity: item.sensitivity};
    });
    return {type: "memory.used", items};
  }
  throw new Error("Invalid stream event");
}

const responseErrorCodes = new Set([
  ...Object.keys(modelMessages.en.errors),
  "MODEL_UNAVAILABLE",
  "INVALID_REQUEST",
  "CONVERSATION_NOT_FOUND",
  "CONVERSATION_CONFLICT",
  "CORE_UNAVAILABLE",
  "STREAM_FAILED", "REQUEST_ABORTED",
]);

async function responseErrorCode(response: Response): Promise<ChatEvent & { type: "error" }> {
  try {
    const value: unknown = await response.json();
    const code = value && typeof value === "object" ? (value as { code?: unknown }).code : undefined;
    if (typeof code === "string" && responseErrorCodes.has(code)) {
      return { type: "error", code: code as Extract<ChatEvent, { type: "error" }>["code"] };
    }
  } catch { /* fall through to the stable transport error */ }
  return { type: "error", code: response.status === 400 ? "INVALID_REQUEST" : "MODEL_UNAVAILABLE" };
}

export class ApiChatTransport implements ChatTransport {
  async *stream(request: ChatRequest, options?: ChatStreamOptions): AsyncIterable<ChatEvent> {
    let response: Response;
    try {
      response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify(request),
        signal: options?.signal,
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      yield { type: "error", code: "MODEL_UNAVAILABLE" };
      return;
    }

    if (!response.ok || !response.body) {
      yield await responseErrorCode(response);
      return;
    }

    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    try {
      while (true) {
        const { value, done } = await reader.read();
        buffer += value ?? "";
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (line.trim()) yield parseEvent(line);
        }
        if (done) break;
      }
      if (buffer.trim()) yield parseEvent(buffer);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      yield { type: "error", code: "STREAM_FAILED" };
    } finally {
      reader.releaseLock();
    }
  }
}

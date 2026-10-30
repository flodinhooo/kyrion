export type ChatRole = "user" | "assistant" | "system";

export type ChatMessage = {
  id: string;
  role: Exclude<ChatRole, "system">;
  content: string;
  createdAt: string;
};

export type ChatRequest = {
  conversationId: string;
  title: string;
  modelId?: string;
  cloudConsent?: boolean;
  message: Pick<ChatMessage, "id" | "content" | "createdAt">;
  locale: "de" | "en";
};

export type ChatErrorCode =
  | "MODEL_UNAVAILABLE"
  | "REQUEST_ABORTED"
  | "INVALID_REQUEST"
  | "CONVERSATION_NOT_FOUND"
  | "CONVERSATION_CONFLICT"
  | "CORE_UNAVAILABLE"
  | "STREAM_FAILED"
  | "CLOUD_NOT_ALLOWED" | "PROVIDER_NOT_CONFIGURED" | "MODEL_DISABLED"
  | "CAPABILITY_UNSUPPORTED" | "PROVIDER_AUTH_FAILED" | "RATE_LIMITED" | "REQUEST_TIMEOUT"
  | "CONTEXT_NOT_ALLOWED" | "CONTEXT_LIMIT_EXCEEDED" | "TOOL_CALL_INVALID" | "PROVIDER_REFUSED"
  | "OUTPUT_LIMIT_REACHED";

export type ChatEvent =
  | { type: "model.selected"; provider: string; modelId: string; profileId: string }
  | { type: "usage"; usage: { inputTokens?: number | null; outputTokens?: number | null; totalTokens?: number | null } }
  | { type: "context.compacted"; estimatedTokens: number; tokenBudget: number }
  | { type: "memory.used"; items: Array<{ id: string; category: string; content: string; sensitivity: "standard" | "sensitive" }> }
  | { type: "message.started"; messageId: string }
  | { type: "message.delta"; messageId: string; delta: string }
  | { type: "message.completed"; messageId: string }
  | { type: "error"; code: ChatErrorCode };

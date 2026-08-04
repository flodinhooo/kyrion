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
  | "STREAM_FAILED";

export type ChatEvent =
  | { type: "context.compacted"; estimatedTokens: number; tokenBudget: number }
  | { type: "memory.used"; items: Array<{ id: string; category: string; content: string; sensitivity: "standard" | "sensitive" }> }
  | { type: "message.started"; messageId: string }
  | { type: "message.delta"; messageId: string; delta: string }
  | { type: "message.completed"; messageId: string }
  | { type: "error"; code: ChatErrorCode };

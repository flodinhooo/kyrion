export type ChatRole = "user" | "assistant" | "system";

export type ChatMessage = {
  id: string;
  role: Exclude<ChatRole, "system">;
  content: string;
  createdAt: string;
};

export type ChatInputMessage = Pick<ChatMessage, "role" | "content">;

export type ChatRequest = {
  conversationId?: string;
  messages: ChatInputMessage[];
  locale: "de" | "en";
};

export type ChatErrorCode =
  | "MODEL_UNAVAILABLE"
  | "REQUEST_ABORTED"
  | "INVALID_REQUEST"
  | "STREAM_FAILED";

export type ChatEvent =
  | { type: "message.started"; messageId: string }
  | { type: "message.delta"; messageId: string; delta: string }
  | { type: "message.completed"; messageId: string }
  | { type: "error"; code: ChatErrorCode };

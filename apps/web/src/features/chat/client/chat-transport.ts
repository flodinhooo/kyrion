import type { ChatEvent, ChatRequest } from "@/features/chat/contracts";

export type ChatStreamOptions = {
  signal?: AbortSignal;
};

export interface ChatTransport {
  stream(request: ChatRequest, options?: ChatStreamOptions): AsyncIterable<ChatEvent>;
}

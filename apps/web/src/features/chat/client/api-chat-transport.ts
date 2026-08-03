import type { ChatTransport, ChatStreamOptions } from "@/features/chat/client/chat-transport";
import type { ChatEvent, ChatRequest } from "@/features/chat/contracts";
import { csrfHeader } from "@/features/auth/csrf";

function parseEvent(line: string): ChatEvent {
  return JSON.parse(line) as ChatEvent;
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
      yield {
        type: "error",
        code: response.status === 400 ? "INVALID_REQUEST" : "MODEL_UNAVAILABLE",
      };
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

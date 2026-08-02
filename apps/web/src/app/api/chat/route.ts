import type { ChatRequest } from "@/features/chat/contracts";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000";

function isChatRequest(value: unknown): value is ChatRequest {
  if (!value || typeof value !== "object") return false;
  const request = value as Partial<ChatRequest>;
  return (request.locale === "de" || request.locale === "en")
    && Array.isArray(request.messages)
    && request.messages.length > 0
    && request.messages.length <= 200
    && request.messages.every((message) =>
      !!message
      && (message.role === "user" || message.role === "assistant")
      && typeof message.content === "string"
      && message.content.trim().length > 0
      && message.content.length <= 100_000,
    );
}

export async function POST(incomingRequest: Request) {
  let body: unknown;
  try {
    body = await incomingRequest.json();
  } catch {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }

  if (!isChatRequest(body)) {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }

  try {
    const response = await fetch(`${AI_SERVICE_URL}/v1/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: incomingRequest.signal,
    });

    if (!response.ok || !response.body) {
      return Response.json({ code: "MODEL_UNAVAILABLE" }, { status: 503 });
    }

    return new Response(response.body, {
      status: 200,
      headers: {
        "Content-Type": "application/x-ndjson",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return Response.json({ code: "MODEL_UNAVAILABLE" }, { status: 503 });
  }
}

import { requireApiSession } from "@/lib/server-auth";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  const body: unknown = await request.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }
  const value = body as { text?: unknown; voiceId?: unknown; locale?: unknown };
  if (typeof value.text !== "string" || value.text.length < 1 || value.text.length > 4_000
    || typeof value.voiceId !== "string" || !/^[a-z0-9_-]{1,40}$/.test(value.voiceId)
    || (value.locale !== "de" && value.locale !== "en")) {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }
  try {
    const response = await fetch(`${AI_SERVICE_URL}/v1/speech/synthesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(value),
      signal: AbortSignal.timeout(120_000),
    });
    if (!response.ok) throw new Error("Synthesis failed");
    return new Response(await response.arrayBuffer(), {
      headers: {
        "Cache-Control": "no-store",
        "Content-Type": "audio/wav",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return Response.json({ code: "TTS_UNAVAILABLE" }, { status: 503 });
  }
}

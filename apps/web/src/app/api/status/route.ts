import type { AiServiceStatus } from "@/features/status/contracts";
import { requireApiSession } from "@/lib/server-auth";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000";
const HEALTH_TIMEOUT_MS = 2_500;

type AiHealthResponse = {
  status: "ok";
  provider: string;
  model: string;
};

function isAiHealthResponse(value: unknown): value is AiHealthResponse {
  if (!value || typeof value !== "object") return false;
  const health = value as Partial<AiHealthResponse>;
  return health.status === "ok"
    && typeof health.provider === "string"
    && health.provider.length > 0
    && typeof health.model === "string"
    && health.model.length > 0;
}

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${AI_SERVICE_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
    });
    if (!response.ok) throw new Error("AI service health request failed");

    const health: unknown = await response.json();
    if (!isAiHealthResponse(health)) throw new Error("AI service health response is invalid");

    const status: AiServiceStatus = { status: "ready", model: health.model };
    return Response.json(status, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    const status: AiServiceStatus = { status: "unavailable" };
    return Response.json(status, {
      headers: { "Cache-Control": "no-store" },
    });
  }
}

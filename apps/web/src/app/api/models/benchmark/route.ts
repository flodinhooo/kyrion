import { isModelBenchmarkResult } from "@/features/models/contracts";
import type { Locale } from "@/lib/messages";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000";

type BenchmarkRequest = { modelId: string; locale: Locale };

function isBenchmarkRequest(value: unknown): value is BenchmarkRequest {
  if (!value || typeof value !== "object") return false;
  const request = value as Partial<BenchmarkRequest>;
  return typeof request.modelId === "string"
    && request.modelId.trim().length > 0
    && request.modelId.length <= 128
    && (request.locale === "de" || request.locale === "en");
}

export async function POST(incomingRequest: Request) {
  let body: unknown;
  try {
    body = await incomingRequest.json();
  } catch {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }

  if (!isBenchmarkRequest(body)) {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }

  try {
    const response = await fetch(`${AI_SERVICE_URL}/v1/models/benchmark`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: incomingRequest.signal,
    });
    const result: unknown = await response.json();
    if (response.status === 400) {
      return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
    }
    if (!response.ok || !isModelBenchmarkResult(result)) {
      throw new Error("Invalid benchmark result");
    }
    return Response.json(result, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ code: "MODEL_UNAVAILABLE" }, { status: 503 });
  }
}

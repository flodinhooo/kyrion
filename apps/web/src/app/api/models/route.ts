import { isModelCatalog } from "@/features/models/contracts";
import { requireApiSession } from "@/lib/server-auth";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${AI_SERVICE_URL}/v1/models`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2_500),
    });
    const catalog: unknown = await response.json();
    if (!response.ok || !isModelCatalog(catalog)) throw new Error("Invalid model catalog");

    return Response.json(catalog, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ code: "MODEL_UNAVAILABLE" }, { status: 503 });
  }
}

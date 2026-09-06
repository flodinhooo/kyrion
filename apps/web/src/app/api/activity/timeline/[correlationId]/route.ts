import { isActivityResponse } from "@/features/activity/contracts";
import { isActionOutcome } from "@/features/actions/contracts";
import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

export async function GET(_request: Request, context: { params: Promise<{ correlationId: string }> }) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  const { correlationId } = await context.params;
  if (!/^[0-9a-f-]{36}$/i.test(correlationId)) return Response.json({ code: "INVALID_ID" }, { status: 400 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/activity/timeline/${correlationId}`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store", signal: AbortSignal.timeout(5_000),
    });
    const body: unknown = await response.json();
    if (!response.ok || !isActivityResponse(body) || !("truncated" in body) || typeof body.truncated !== "boolean") throw new Error("Invalid timeline");
    if ("outcome" in body && body.outcome !== null && !isActionOutcome(body.outcome)) throw new Error("Invalid outcome");
    return Response.json(body, { headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

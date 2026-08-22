import { isMotionEventList } from "@/features/devices/contracts";
import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

export async function GET(_request: Request, context: RouteContext<"/api/devices/[id]/motion-events">) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  const { id } = await context.params;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/devices/${encodeURIComponent(id)}/motion-events`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    const value: unknown = await response.json().catch(() => null);
    return response.ok && isMotionEventList(value)
      ? Response.json(value, { headers: { "Cache-Control": "no-store" } })
      : Response.json(value ?? { code: "CORE_UNAVAILABLE" }, { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

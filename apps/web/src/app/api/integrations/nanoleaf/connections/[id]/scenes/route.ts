import { isNanoleafScenes } from "@/features/integrations/contracts";
import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

export async function GET(_request: Request, context: RouteContext<"/api/integrations/nanoleaf/connections/[id]/scenes">) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  const { id } = await context.params;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/nanoleaf/connections/${id}/scenes`, { headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store" });
    const value: unknown = await response.json().catch(() => ({}));
    return response.ok && isNanoleafScenes(value) ? Response.json(value, { headers: { "Cache-Control": "no-store" } }) : Response.json(value, { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

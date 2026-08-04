import { isNanoleafState } from "@/features/integrations/contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function PUT(request: Request, context: RouteContext<"/api/integrations/nanoleaf/connections/[id]/brightness">) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const { id } = await context.params;
  let body: unknown; try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/nanoleaf/connections/${id}/brightness`, { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` }, body: JSON.stringify(body), cache: "no-store" });
    const value: unknown = await response.json().catch(() => ({}));
    return response.ok && isNanoleafState(value) ? Response.json(value) : Response.json(value, { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

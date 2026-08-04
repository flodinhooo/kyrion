import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function DELETE(request: Request, context: RouteContext<"/api/integrations/nanoleaf/connections/[id]">) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const { id } = await context.params;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/nanoleaf/connections/${id}`, { method: "DELETE", headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store" });
    return response.ok ? new Response(null, { status: 204 }) : Response.json(await response.json().catch(() => ({})), { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

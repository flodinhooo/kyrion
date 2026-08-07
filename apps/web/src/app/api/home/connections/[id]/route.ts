import { isConnection } from "@/features/integrations/contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function PATCH(request: Request, context: RouteContext<"/api/home/connections/[id]">) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const { id } = await context.params;
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/home/connections/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify(body),
    });
    const value: unknown = await response.json().catch(() => ({}));
    return response.ok && isConnection(value) ? Response.json(value) : Response.json(value, { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

import { isConnection } from "@/features/integrations/contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function GET(_: Request, context: RouteContext<"/api/gateways/[id]/bluetooth/devices">) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  const { id } = await context.params;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/gateways/${id}/bluetooth/devices`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    const value: unknown = await response.json().catch(() => []);
    return Array.isArray(value) ? Response.json(value, { status: response.status })
      : Response.json({ code: "INVALID_RESPONSE" }, { status: 502 });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

export async function POST(request: Request, context: RouteContext<"/api/gateways/[id]/bluetooth/devices">) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const { id } = await context.params;
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/gateways/${id}/bluetooth/devices`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify(body),
    });
    const value: unknown = await response.json().catch(() => ({}));
    return response.ok && isConnection(value) ? Response.json(value, { status: 201 })
      : Response.json(value, { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

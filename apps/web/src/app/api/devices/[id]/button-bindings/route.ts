import { isButtonBindingList } from "@/features/devices/contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function GET(_request: Request, context: RouteContext<"/api/devices/[id]/button-bindings">) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  const { id } = await context.params;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/devices/${encodeURIComponent(id)}/button-bindings`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    const value: unknown = await response.json().catch(() => null);
    return response.ok && isButtonBindingList(value)
      ? Response.json(value, { headers: { "Cache-Control": "no-store" } })
      : Response.json(value ?? { code: "CORE_UNAVAILABLE" }, { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

export async function PUT(request: Request, context: RouteContext<"/api/devices/[id]/button-bindings">) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const { id } = await context.params;
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/devices/${encodeURIComponent(id)}/button-bindings`, {
      method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify(body),
    });
    const value: unknown = await response.json().catch(() => null);
    return response.ok && isButtonBindingList(value)
      ? Response.json(value)
      : Response.json(value ?? { code: "CORE_UNAVAILABLE" }, { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

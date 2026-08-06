import { csrfIsValid, CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

const actions = new Set(["pairing", "power", "brightness", "color"]);

export async function POST(request: Request, context: RouteContext<"/api/gateways/[id]/zigbee/[action]">) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const { id, action } = await context.params;
  if (!actions.has(action)) return Response.json({ code: "NOT_FOUND" }, { status: 404 });
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/gateways/${id}/zigbee/${action}`, {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify(body),
    });
    const value: unknown = await response.json().catch(() => ({}));
    return Response.json(value, { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

import { isConnection, isConnectionList } from "@/features/integrations/contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function GET() {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/nanoleaf/connections`, { headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store" });
    const value: unknown = await response.json();
    return response.ok && isConnectionList(value) ? Response.json(value, { headers: { "Cache-Control": "no-store" } }) : Response.json(value, { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

export async function POST(request: Request) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  let body: unknown; try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/nanoleaf/connections`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` }, body: JSON.stringify(body), cache: "no-store" });
    const value: unknown = await response.json().catch(() => ({}));
    return response.ok && isConnection(value) ? Response.json(value, { status: 201 }) : Response.json(value, { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

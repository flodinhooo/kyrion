import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

type Context = { params: Promise<{ id: string }> };

export async function GET(_: Request, context: Context) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  const { id } = await context.params;
  return forward(id, auth.token);
}

export async function PUT(request: Request, context: Context) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const { id } = await context.params;
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  return forward(id, auth.token, body);
}

async function forward(id: string, token: string, body?: unknown) {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/conversations/${id}`, {
      method: body === undefined ? "GET" : "PUT",
      headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
    });
    const value: unknown = await response.json().catch(() => ({}));
    return Response.json(value, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

type Context = { params: Promise<{ id: string }> };

export async function PATCH(request: Request, context: Context) {
  return mutate(request, context, "PATCH");
}

export async function DELETE(request: Request, context: Context) {
  return mutate(request, context, "DELETE");
}

async function mutate(request: Request, context: Context, method: "PATCH" | "DELETE") {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const { id } = await context.params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  let body: unknown;
  if (method === "PATCH") { try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); } }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/memory/${id}`, {
      method, headers: { Authorization: `Bearer ${auth.token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined, cache: "no-store",
    });
    if (response.status === 204) return new Response(null, { status: 204 });
    return Response.json(await response.json(), { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

type Context = { params: Promise<{ id: string }> };

async function mutate(request: Request, context: Context, method: "PUT" | "DELETE") {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!await csrfIsValid(request)) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const { id } = await context.params;
  if (!/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(id)) return Response.json({ code: "HOUSEHOLD_CALENDAR_INVALID" }, { status: 400 });
  const query = new URLSearchParams();
  if (method === "DELETE") query.set("revision", new URL(request.url).searchParams.get("revision") ?? "");
  if (method === "DELETE" && new URL(request.url).searchParams.has("retainExternalCopies"))
    query.set("retainExternalCopies", new URL(request.url).searchParams.get("retainExternalCopies") ?? "");
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/calendar/household-events/${id}${query.size ? `?${query}` : ""}`, {
      method, headers: { Authorization: `Bearer ${auth.token}`, ...(method === "PUT" ? { "Content-Type": "application/json" } : {}) },
      ...(method === "PUT" ? { body: await request.text() } : {}), cache: "no-store", signal: AbortSignal.timeout(10_000),
    });
    if (method === "DELETE" && response.ok) return new Response(null, { status: 204 });
    return Response.json(await response.json(), { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

export function PUT(request: Request, context: Context) { return mutate(request, context, "PUT"); }
export function DELETE(request: Request, context: Context) { return mutate(request, context, "DELETE"); }

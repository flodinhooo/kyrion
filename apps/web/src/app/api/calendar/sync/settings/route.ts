import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

async function proxy(request?: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (request && !(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/calendar/sync/settings`, {
      method: request ? "PUT" : "GET", cache: "no-store",
      headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" },
      ...(request ? { body: await request.text() } : {}),
    });
    return Response.json(await response.json(), { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}
export async function GET() { return proxy(); }
export async function PUT(request: Request) { return proxy(request); }

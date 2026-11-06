import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function POST(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!await csrfIsValid(request)) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/calendar/household-events`, {
      method: "POST", headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" },
      body: await request.text(), cache: "no-store", signal: AbortSignal.timeout(10_000),
    });
    return Response.json(await response.json(), { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

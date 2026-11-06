import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function disclosureProxy(path: string, request?: Request, write = false) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (write && (!request || !await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/calendar/personal-disclosure${path}`, {
      method: write ? "PUT" : "GET",
      headers: { Authorization: `Bearer ${auth.token}`, ...(write ? { "Content-Type": "application/json" } : {}) },
      ...(write ? { body: await request!.text() } : {}), cache: "no-store", signal: AbortSignal.timeout(20_000),
    });
    return Response.json(await response.json(), { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503, headers: { "Cache-Control": "no-store" } }); }
}

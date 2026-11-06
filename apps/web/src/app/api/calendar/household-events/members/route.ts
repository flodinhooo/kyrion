import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/calendar/household-events/members`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store", signal: AbortSignal.timeout(10_000),
    });
    return Response.json(await response.json(), { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

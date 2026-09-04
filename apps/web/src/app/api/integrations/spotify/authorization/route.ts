import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function POST(request: Request) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  try { const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/spotify/authorization`, { method: "POST", headers: { Authorization: `Bearer ${auth.token}` } }); return Response.json(await response.json().catch(() => ({})), { status: response.status }); }
  catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

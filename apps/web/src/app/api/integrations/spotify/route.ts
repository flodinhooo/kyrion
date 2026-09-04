import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function GET() {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  try { const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/spotify`, { headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store" }); return Response.json(await response.json(), { status: response.status }); }
  catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

export async function DELETE(request: Request) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  try { const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/spotify`, { method: "DELETE", headers: { Authorization: `Bearer ${auth.token}` } }); return response.ok ? new Response(null, { status: 204 }) : Response.json(await response.json().catch(() => ({})), { status: response.status }); }
  catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

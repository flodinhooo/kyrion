import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";
export async function POST(request: Request) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  try { const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/home-assistant/probe`, { method: "POST", headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" }, body: await request.text(), cache: "no-store" }); return Response.json(await response.json().catch(() => ({ code: "INTERNAL_ERROR" })), { status: response.status }); }
  catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

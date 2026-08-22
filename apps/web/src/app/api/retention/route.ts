import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function GET() {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/retention`, { headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store" });
    return Response.json(await response.json(), { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

export async function PUT(request: Request) {
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  let body: unknown; try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/retention`, {
      method: "PUT", headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body), cache: "no-store",
    });
    return Response.json(await response.json().catch(() => ({})), { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

export async function GET() {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/retention/preview`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    return Response.json(await response.json().catch(() => ({})), { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

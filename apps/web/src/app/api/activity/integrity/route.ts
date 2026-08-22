import { requireApiSession } from "@/lib/server-auth";

const CORE_SERVICE_URL = process.env.CORE_SERVICE_URL ?? "http://127.0.0.1:8080";

export async function GET() {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/activity/integrity`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store", signal: AbortSignal.timeout(2_500),
    });
    return Response.json(await response.json().catch(() => ({})), { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

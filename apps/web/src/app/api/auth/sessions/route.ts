import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/auth/sessions`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    const value: unknown = await response.json().catch(() => ({}));
    return Response.json(value, { status: response.status });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

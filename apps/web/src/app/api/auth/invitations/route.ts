import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function POST(request: Request) {
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/auth/invitations`, {
      method: "POST", headers: { Authorization: `Bearer ${auth.token}` },
      cache: "no-store", signal: AbortSignal.timeout(10_000),
    });
    const value: unknown = await response.json();
    return Response.json(value, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

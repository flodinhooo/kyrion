import { isActionOutcome, isWebActionRequest } from "@/features/actions/contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function POST(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  if (!isWebActionRequest(body)) return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: request.signal,
    });
    const value: unknown = await response.json().catch(() => null);
    if (!response.ok) return Response.json(value ?? { code: "CORE_UNAVAILABLE" }, { status: response.status });
    return isActionOutcome(value)
      ? Response.json(value, { headers: { "Cache-Control": "no-store" } })
      : Response.json({ code: "CORE_UNAVAILABLE" }, { status: 502 });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

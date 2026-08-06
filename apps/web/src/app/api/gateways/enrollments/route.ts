import { isGatewayEnrollment } from "@/features/gateways/contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function POST(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const body: unknown = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || typeof (body as { displayName?: unknown }).displayName !== "string") {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/gateways/enrollments`, {
      method: "POST",
      headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body), cache: "no-store", signal: request.signal,
    });
    const value: unknown = await response.json().catch(() => null);
    return response.ok && isGatewayEnrollment(value)
      ? Response.json(value, { status: 201, headers: { "Cache-Control": "no-store" } })
      : Response.json(value ?? { code: "CORE_UNAVAILABLE" }, { status: response.status });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

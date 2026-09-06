import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { diagnosticReasons } from "@/features/system-services/contracts";

export async function POST(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/home-assistant/sync`, {
      method: "POST", headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store", signal: AbortSignal.timeout(20_000),
    });
    const body: unknown = await response.json();
    if (response.ok && body && typeof body === "object" && "imported" in body && Number.isInteger(body.imported)
      && "correlationId" in body && typeof body.correlationId === "string" && "reason" in body
      && (body.reason === null || diagnosticReasons.some((reason) => reason === body.reason))) return Response.json(body);
    return Response.json({ code: "dependency_error" }, { status: 502 });
  } catch { return Response.json({ code: "dependency_unreachable" }, { status: 503 }); }
}

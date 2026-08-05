import { isRuntimeDeviceList } from "@/features/devices/contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function POST(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) {
    return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/devices/observations/refresh`, {
      method: "POST",
      headers: { Authorization: `Bearer ${auth.token}` },
      cache: "no-store",
      signal: request.signal,
    });
    const value: unknown = await response.json().catch(() => null);
    return response.ok && isRuntimeDeviceList(value)
      ? Response.json(value, { headers: { "Cache-Control": "no-store" } })
      : Response.json(value ?? { code: "CORE_UNAVAILABLE" }, { status: response.status });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

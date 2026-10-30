import {CORE_SERVICE_URL, csrfIsValid, requireApiSession} from "@/lib/server-auth";

export async function PATCH(request: Request, context: { params: Promise<{ id: string }> }) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({code: "CSRF_INVALID"}, {status: 403});
  const {id} = await context.params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) return Response.json({code: "INVALID_REQUEST"}, {status: 400});
  try {
    const body = await request.text();
    if (body.length > 64000) return Response.json({code: "INVALID_REQUEST"}, {status: 400});
    const response = await fetch(`${CORE_SERVICE_URL}/v1/memory/${id}/validity`, {
      method: "PATCH",
      headers: {"Content-Type": "application/json", Authorization: `Bearer ${auth.token}`}, body, cache: "no-store",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(10000)])
    });
    return Response.json(await response.json(), {status: response.status});
  } catch {
    return Response.json({code: "CORE_UNAVAILABLE"}, {status: 503});
  }
}

import {CORE_SERVICE_URL, csrfIsValid, requireApiSession} from "@/lib/server-auth";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({code: "CSRF_INVALID"}, {status: 403});
  const {id} = await context.params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) return Response.json({code: "INVALID_REQUEST"}, {status: 400});
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/memory/${id}/reject`, {
      method: "POST",
      headers: {Authorization: `Bearer ${auth.token}`},
      cache: "no-store",
      signal: AbortSignal.timeout(10000)
    });
    return response.status === 204 ? new Response(null, {status: 204}) : Response.json(await response.json(), {status: response.status});
  } catch {
    return Response.json({code: "CORE_UNAVAILABLE"}, {status: 503});
  }
}

import {CORE_SERVICE_URL, requireApiSession} from "@/lib/server-auth";

export async function GET(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/memory/context${new URL(request.url).search}`, {
      method: "GET", headers: {"Content-Type": "application/json", Authorization: `Bearer ${auth.token}`},
      cache: "no-store", signal: AbortSignal.any([request.signal, AbortSignal.timeout(10000)]),
    });
    return Response.json(await response.json(), {status: response.status});
  } catch {
    return Response.json({code: "CORE_UNAVAILABLE"}, {status: 503});
  }
}

import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function spaceProxy(request: Request, path: string) {
  if (request.method !== "GET" && !(await csrfIsValid(request))) {
    return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  }
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}${path}`, {
      method: request.method,
      headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" },
      ...(request.method === "PUT" || request.method === "POST" ? { body: await request.text() } : {}),
      cache: "no-store", signal: AbortSignal.timeout(10_000),
    });
    return new Response(response.status === 204 ? null : await response.text(), {
      status: response.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

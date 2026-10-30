import {CORE_SERVICE_URL, csrfIsValid, requireApiSession} from "@/lib/server-auth";

type Context = { params: Promise<{ operation: string }> };

async function forward(request: Request, context: Context, method: "GET" | "PUT") {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  const {operation} = await context.params;
  if (!["preferences", "policy", "usage"].includes(operation) || (method === "PUT" && operation === "usage")) {
    return Response.json({code: "INVALID_REQUEST"}, {status: 404});
  }
  if (method === "PUT" && !(await csrfIsValid(request))) return Response.json({code: "CSRF_INVALID"}, {status: 403});
  const body = method === "PUT" ? await request.text() : undefined;
  if (body && body.length > 64000) return Response.json({code: "INVALID_REQUEST"}, {status: 400});
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/ai/${operation}`, {
      method,
      headers: {Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json"},
      ...(body ? {body} : {}),
      cache: "no-store",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(10_000)]),
    });
    const value: unknown = await response.json();
    return Response.json(value, {status: response.status, headers: {"Cache-Control": "no-store"}});
  } catch {
    return Response.json({code: "CORE_UNAVAILABLE"}, {status: 503});
  }
}

export const GET = (request: Request, context: Context) => forward(request, context, "GET");
export const PUT = (request: Request, context: Context) => forward(request, context, "PUT");

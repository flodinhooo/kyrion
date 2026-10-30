import {CORE_SERVICE_URL, csrfIsValid, requireApiSession} from "@/lib/server-auth";

const allowed = /^(spaces|spaces\/[0-9a-f-]{36}\/documents|documents\/[0-9a-f-]{36}(\/(content|reindex))?|search|answers\/[0-9a-f-]{36})$/;

async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (request.method !== "GET" && !(await csrfIsValid(request)))
    return Response.json({code: "CSRF_INVALID"}, {status: 403});
  const path = (await context.params).path.join("/");
  if (!allowed.test(path)) return Response.json({code: "KNOWLEDGE_NOT_FOUND"}, {status: 404});
  const headers = new Headers({Authorization: `Bearer ${auth.token}`});
  const type = request.headers.get("content-type");
  if (type) headers.set("content-type", type);
  let size = 0;
  const body = request.body?.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      size += chunk.byteLength;
      if (size > 51_000_000) throw new Error("KNOWLEDGE_TOO_LARGE");
      controller.enqueue(chunk);
    },
  }));
  const init: RequestInit & { duplex: "half" } = {
    method: request.method, headers,
    body: request.method === "GET" ? undefined : body, duplex: "half", cache: "no-store",
    signal: AbortSignal.any([request.signal, AbortSignal.timeout(60_000)])
  };
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/knowledge/${path}${new URL(request.url).search}`, init);
    const returned = new Headers({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"});
    for (const key of ["content-type", "content-disposition"]) {
      const value = response.headers.get(key);
      if (value) returned.set(key, value);
    }
    return new Response(response.body, {status: response.status, headers: returned});
  } catch {
    return Response.json({code: size > 51_000_000 ? "KNOWLEDGE_TOO_LARGE" : "CORE_UNAVAILABLE"},
      {status: size > 51_000_000 ? 413 : 503});
  }
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;

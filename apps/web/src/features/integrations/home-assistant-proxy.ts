import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

async function limitedText(body: ReadableStream<Uint8Array> | null, maximum: number): Promise<string> {
  if (!body) return "";
  const reader = body.getReader();
  const parts: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const next = await reader.read();
    if (next.done) break;
    size += next.value.byteLength;
    if (size > maximum) { await reader.cancel(); throw new Error("REQUEST_TOO_LARGE"); }
    parts.push(next.value);
  }
  const result = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) { result.set(part, offset); offset += part.byteLength; }
  return new TextDecoder("utf-8", { fatal: true }).decode(result);
}

export async function proxyHa(request: Request, operation: "preview" | "selection") {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (request.method !== "GET" && request.method !== "POST") return Response.json({ code: "METHOD_NOT_ALLOWED" }, { status: 405 });
  if (request.method === "POST" && !(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  try {
    const body = request.method === "POST" ? await limitedText(request.body, 256 * 1024) : undefined;
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/home-assistant/${operation}`, {
      method: request.method, headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" },
      body, cache: "no-store", signal: AbortSignal.timeout(45_000),
    });
    const value: unknown = JSON.parse(await limitedText(response.body, 2 * 1024 * 1024));
    if (!response.ok) {
      const code = value !== null && typeof value === "object" && "code" in value && typeof value.code === "string" && /^[A-Za-z_]{1,100}$/.test(value.code) ? value.code : "CORE_UNAVAILABLE";
      return Response.json({ code }, { status: response.status, headers: { "Cache-Control": "no-store" } });
    }
    return Response.json(value, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const large = error instanceof Error && error.message === "REQUEST_TOO_LARGE";
    return Response.json({ code: large ? "REQUEST_TOO_LARGE" : "CORE_UNAVAILABLE" }, { status: large ? 413 : 503 });
  }
}

// Proxy only: the independent host helper owns operator authorisation/execution.
export const runtime = "nodejs";

export async function POST(request: Request) {
  const url = new URL(request.url);
  if (process.env.NODE_ENV !== "development" || url.protocol !== "http:"
    || !["localhost", "127.0.0.1"].includes(url.hostname) || url.port !== "3000"
    || request.headers.get("origin") !== url.origin) {
    return Response.json({code: "RECOVERY_LOCAL_ONLY"}, {status: 403});
  }
  try {
    const reader = request.body?.getReader();
    if (!reader) return Response.json({code: "INVALID_REQUEST"}, {status: 400});
    const chunks: Uint8Array[] = [];
    let length = 0;
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      length += value.length;
      if (length > 512) {
        await reader.cancel();
        return Response.json({code: "INVALID_REQUEST"}, {status: 413});
      }
      chunks.push(value);
    }
    const body: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (!body || typeof body !== "object" || !("key" in body) || typeof body.key !== "string"
      || !/^[a-f0-9]{64}$/.test(body.key) || !("action" in body) || typeof body.action !== "string"
      || !["start", "restart", "status"].includes(body.action)
      || Object.keys(body).length !== 2) return Response.json({code: "INVALID_REQUEST"}, {status: 400});
    const result = await fetch("http://127.0.0.1:17654/", {
      method: body.action === "status" ? "GET" : "POST",
      headers: {Authorization: `Bearer ${body.key}`, "Content-Type": "application/json"},
      ...(body.action === "status" ? {} : {body: JSON.stringify({action: body.action})}),
      cache: "no-store", signal: AbortSignal.timeout(3000),
    });
    return Response.json(await result.json(), {status: result.status, headers: {"Cache-Control": "no-store"}});
  } catch {
    return Response.json({code: "RECOVERY_HELPER_UNAVAILABLE"}, {status: 503});
  }
}

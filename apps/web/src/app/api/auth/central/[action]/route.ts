import { cookies } from "next/headers";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession, secureCookie, sessionToken } from "@/lib/server-auth";
import { setAuthCookies } from "../../session-cookie";
import { isCentralDevice, isCentralStatus } from "@/features/auth/central-contracts";

const FLOW_COOKIE = "kyrion_central_operation";
const FLOW_PATH = "/api/auth/central";
type Context = { params: Promise<{ action: string }> };
const error = (code: string, status: number) => Response.json({ code }, { status, headers: { "Cache-Control": "no-store" } });

async function forward(request: Request, context: Context) {
  const { action } = await context.params;
  if (!({ config: ["GET"], status: ["GET"], start: ["POST"], poll: ["POST"], complete: ["POST"], cancel: ["POST"], link: ["DELETE"] } as Record<string, string[]>)[action]?.includes(request.method)) return error("NOT_FOUND", 404);
  if (request.method !== "GET") {
    const origin = request.headers.get("origin");
    // Next may normalize request.url to its listening hostname. The original
    // Host remains the browser's authority, including behind a TLS proxy.
    const host = request.headers.get("host") ?? new URL(request.url).host;
    try {
      if (origin && new URL(origin).host !== host) return error("CSRF_INVALID", 403);
    } catch { return error("CSRF_INVALID", 403); }
    if (!(await csrfIsValid(request))) return error("CSRF_INVALID", 403);
  }
  let body: Record<string, unknown> = {};
  if (request.method !== "GET") {
    try {
      const value: unknown = await request.json();
      if (!value || typeof value !== "object" || Array.isArray(value)) return error("INVALID_REQUEST", 400);
      body = value as Record<string, unknown>;
    } catch { return error("INVALID_REQUEST", 400); }
  }
  let token = await sessionToken();
  if (action === "status" || action === "link" || (action === "start" && body.mode === "LINK")) {
    const auth = await requireApiSession();
    if (auth instanceof Response) return auth;
    token = auth.token;
  }
  const store = await cookies();
  if (["poll", "complete", "cancel"].includes(action)) {
    const operationToken = store.get(FLOW_COOKIE)?.value;
    if (!operationToken) return error("CENTRAL_OPERATION_INVALID", 400);
    // The browser never chooses or sees an operation credential.
    body = { operationToken, ...(action === "complete" ? { confirm: body.confirm === true } : {}) };
  } else if (action === "start") {
    if (body.mode !== "LOGIN" && body.mode !== "LINK") return error("INVALID_REQUEST", 400);
    body = { mode: body.mode, ...(body.mode === "LINK" ? { currentPassword: body.currentPassword } : {}) };
  } else if (action === "link") body = { currentPassword: body.currentPassword };
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/auth/central/${action}`, {
      method: request.method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(request.method !== "GET" ? { body: JSON.stringify(body) } : {}), cache: "no-store", signal: AbortSignal.timeout(15_000),
    });
    if (response.status === 204) {
      if (action === "cancel") store.set(FLOW_COOKIE, "", { httpOnly: true, secure: secureCookie(), sameSite: "strict", path: FLOW_PATH, maxAge: 0 });
      return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
    }
    const value: unknown = await response.json();
    if (!response.ok) {
      const code = value && typeof value === "object" && "code" in value && typeof value.code === "string" ? value.code : "CENTRAL_INVALID_RESPONSE";
      return error(code, response.status);
    }
    if (action === "start") {
      if (!isCentralDevice(value) || !("operationToken" in value) || typeof value.operationToken !== "string") return error("CENTRAL_INVALID_RESPONSE", 502);
      const { userCode, verificationUri, expiresAt, interval } = value;
      store.set(FLOW_COOKIE, value.operationToken, { httpOnly: true, secure: secureCookie(), sameSite: "strict", path: FLOW_PATH, expires: new Date(expiresAt) });
      return Response.json({ userCode, verificationUri, expiresAt, interval }, { headers: { "Cache-Control": "no-store" } });
    }
    if (action === "complete") {
      if (!value || typeof value !== "object") return error("CENTRAL_INVALID_RESPONSE", 502);
      if ("sessionToken" in value) {
        if (typeof value.sessionToken !== "string" || !("expiresAt" in value) || typeof value.expiresAt !== "string") return error("CENTRAL_INVALID_RESPONSE", 502);
        await setAuthCookies(value.sessionToken, value.expiresAt);
      } else if (!("linked" in value) || value.linked !== true) return error("CENTRAL_INVALID_RESPONSE", 502);
      store.set(FLOW_COOKIE, "", { httpOnly: true, secure: secureCookie(), sameSite: "strict", path: FLOW_PATH, maxAge: 0 });
      return Response.json({ completed: true }, { headers: { "Cache-Control": "no-store" } });
    }
    let result: unknown;
    if (action === "config") {
      if (!value || typeof value !== "object" || !("enabled" in value) || typeof value.enabled !== "boolean") return error("CENTRAL_INVALID_RESPONSE", 502);
      result = { enabled: value.enabled };
    } else if (action === "status") {
      if (!isCentralStatus(value)) return error("CENTRAL_INVALID_RESPONSE", 502);
      result = { linked: value.linked, ...(value.issuer ? { issuer: value.issuer } : {}) };
    } else if (action === "poll") {
      if (!value || typeof value !== "object" || !("status" in value) || !["PENDING", "CONFIRM"].includes(String(value.status))) return error("CENTRAL_INVALID_RESPONSE", 502);
      result = { status: value.status };
    } else return error("CENTRAL_INVALID_RESPONSE", 502);
    return Response.json(result, { headers: { "Cache-Control": "no-store" } });
  } catch { return error("CORE_UNAVAILABLE", 503); }
}
export const GET = forward;
export const POST = forward;
export const DELETE = forward;

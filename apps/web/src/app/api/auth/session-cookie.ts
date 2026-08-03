import { randomBytes } from "node:crypto";
import { cookies } from "next/headers";
import { CORE_SERVICE_URL, CSRF_COOKIE, secureCookie, SESSION_COOKIE } from "@/lib/server-auth";

export async function setAuthCookies(sessionToken: string, expiresAt: string) {
  const store = await cookies();
  const secure = secureCookie();
  store.set(SESSION_COOKIE, sessionToken, {
    httpOnly: true, sameSite: "strict", secure, path: "/", expires: new Date(expiresAt),
  });
  store.set(CSRF_COOKIE, randomBytes(32).toString("base64url"), {
    httpOnly: false, sameSite: "strict", secure, path: "/", expires: new Date(expiresAt),
  });
}

export async function clearAuthCookies() {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
  store.delete(CSRF_COOKIE);
}

export async function authenticate(request: Request, path: string, successStatus: number) {
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store",
    });
    const value: unknown = await response.json();
    if (!response.ok) return Response.json(value, { status: response.status });
    const session = value as { user?: unknown; sessionToken?: unknown; expiresAt?: unknown };
    if (typeof session.sessionToken !== "string" || typeof session.expiresAt !== "string") {
      return Response.json({ code: "AUTH_SERVICE_INVALID_RESPONSE" }, { status: 502 });
    }
    await setAuthCookies(session.sessionToken, session.expiresAt);
    return Response.json({ user: session.user }, { status: successStatus });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

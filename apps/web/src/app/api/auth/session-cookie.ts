import { randomBytes } from "node:crypto";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { CORE_SERVICE_URL, CSRF_COOKIE, secureCookie, SESSION_COOKIE } from "@/lib/server-auth";
import { csrfCookieOptions, sessionCookieOptions } from "@/lib/auth-security";

export async function setAuthCookies(sessionToken: string, expiresAt: string) {
  const store = await cookies();
  const secure = secureCookie();
  const expires = new Date(expiresAt);
  store.set(SESSION_COOKIE, sessionToken, sessionCookieOptions(expires, secure));
  store.set(CSRF_COOKIE, randomBytes(32).toString("base64url"), csrfCookieOptions(expires, secure));
}

export async function clearAuthCookies() {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
  store.delete(CSRF_COOKIE);
}

export async function authenticate(request: Request, path: string, successStatus: number) {
  let body: unknown;
  const isBrowserForm = request.headers.get("content-type")
    ?.toLowerCase()
    .startsWith("application/x-www-form-urlencoded") ?? false;
  try {
    if (isBrowserForm) {
      const form = await request.formData();
      body = { username: form.get("username"), password: form.get("password"),
        ...(path === "/v1/auth/register" ? { invitationCode: form.get("invitationCode") } : {}) };
    } else {
      body = await request.json();
    }
  } catch {
    return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    const value: unknown = await response.json();
    if (!response.ok) return Response.json(value, { status: response.status });
    const session = value as { user?: unknown; sessionToken?: unknown; expiresAt?: unknown };
    if (typeof session.sessionToken !== "string" || typeof session.expiresAt !== "string") {
      return Response.json({ code: "AUTH_SERVICE_INVALID_RESPONSE" }, { status: 502 });
    }
    if (isBrowserForm) {
      const response = NextResponse.redirect(new URL("/", request.url), 303);
      const expires = new Date(session.expiresAt);
      const secure = secureCookie();
      response.cookies.set(SESSION_COOKIE, session.sessionToken, sessionCookieOptions(expires, secure));
      response.cookies.set(
        CSRF_COOKIE,
        randomBytes(32).toString("base64url"),
        csrfCookieOptions(expires, secure),
      );
      return response;
    }
    await setAuthCookies(session.sessionToken, session.expiresAt);
    return Response.json({ user: session.user }, { status: successStatus });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

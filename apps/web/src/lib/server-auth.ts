import { cookies } from "next/headers";
import { csrfTokensMatch } from "@/lib/auth-security";

export const SESSION_COOKIE = "kyrion_session";
export const CSRF_COOKIE = "kyrion_csrf";
export const CORE_SERVICE_URL = process.env.CORE_SERVICE_URL ?? "http://127.0.0.1:8080";

export type AuthUser = { id: string; username: string; canInvite?: boolean };
type UserLookup = { user: AuthUser | null; unavailable: boolean };

export async function sessionToken(): Promise<string | null> {
  return (await cookies()).get(SESSION_COOKIE)?.value ?? null;
}

export async function currentUser(): Promise<AuthUser | null> {
  return (await lookupUser()).user;
}

async function lookupUser(): Promise<UserLookup> {
  const token = await sessionToken();
  if (!token) return { user: null, unavailable: false };
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) return { user: null, unavailable: response.status !== 401 && response.status !== 403 };
    const value: unknown = await response.json();
    if (!value || typeof value !== "object") return { user: null, unavailable: true };
    const user = value as Partial<AuthUser>;
    return typeof user.id === "string" && typeof user.username === "string"
      ? { user: { id: user.id, username: user.username, ...(typeof user.canInvite === "boolean" ? { canInvite: user.canInvite } : {}) }, unavailable: false }
      : { user: null, unavailable: true };
  } catch {
    return { user: null, unavailable: true };
  }
}

export async function isSetupRequired(): Promise<boolean | null> {
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/auth/setup/status`, { cache: "no-store", signal: AbortSignal.timeout(5_000) });
    if (!response.ok) return null;
    const value: unknown = await response.json();
    return value && typeof value === "object" && typeof (value as { setupRequired?: unknown }).setupRequired === "boolean"
      ? (value as { setupRequired: boolean }).setupRequired
      : null;
  } catch {
    return null;
  }
}

export async function requireApiSession(): Promise<{ token: string; user: AuthUser } | Response> {
  const token = await sessionToken();
  const { user, unavailable } = await lookupUser();
  if (unavailable) return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  return token && user
    ? { token, user }
    : Response.json({ code: "UNAUTHENTICATED" }, { status: 401 });
}

export async function csrfIsValid(request: Request): Promise<boolean> {
  const cookieToken = (await cookies()).get(CSRF_COOKIE)?.value;
  const headerToken = request.headers.get("x-kyrion-csrf");
  return csrfTokensMatch(cookieToken, headerToken);
}

export function secureCookie() {
  if (process.env.KYRION_INSECURE_LAN_HTTP === "true") return false;
  return process.env.NODE_ENV === "production" || process.env.KYRION_HTTPS === "true";
}

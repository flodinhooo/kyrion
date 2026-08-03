import { cookies } from "next/headers";
import { csrfTokensMatch } from "@/lib/auth-security";

export const SESSION_COOKIE = "kyrion_session";
export const CSRF_COOKIE = "kyrion_csrf";
export const CORE_SERVICE_URL = process.env.CORE_SERVICE_URL ?? "http://127.0.0.1:8080";

export type AuthUser = { id: string; username: string };

export async function sessionToken(): Promise<string | null> {
  return (await cookies()).get(SESSION_COOKIE)?.value ?? null;
}

export async function currentUser(): Promise<AuthUser | null> {
  const token = await sessionToken();
  if (!token) return null;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) return null;
    const value: unknown = await response.json();
    if (!value || typeof value !== "object") return null;
    const user = value as Partial<AuthUser>;
    return typeof user.id === "string" && typeof user.username === "string"
      ? { id: user.id, username: user.username }
      : null;
  } catch {
    return null;
  }
}

export async function isSetupRequired(): Promise<boolean | null> {
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/auth/setup/status`, { cache: "no-store" });
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
  const user = await currentUser();
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
  return process.env.NODE_ENV === "production" || process.env.KYRION_HTTPS === "true";
}

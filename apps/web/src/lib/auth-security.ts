import { timingSafeEqual } from "node:crypto";

export function csrfTokensMatch(cookieToken?: string, headerToken?: string | null): boolean {
  if (!cookieToken || !headerToken) return false;
  const left = Buffer.from(cookieToken);
  const right = Buffer.from(headerToken);
  return left.length === right.length && timingSafeEqual(left, right);
}

export function sessionCookieOptions(expires: Date, secure: boolean) {
  // OAuth returns through a cross-site top-level navigation. Lax makes the
  // session available to that GET callback while unsafe cross-site requests
  // remain excluded and mutations still require the separate CSRF token.
  return { httpOnly: true, sameSite: "lax" as const, secure, path: "/", expires };
}

export function csrfCookieOptions(expires: Date, secure: boolean) {
  return { httpOnly: false, sameSite: "strict" as const, secure, path: "/", expires };
}

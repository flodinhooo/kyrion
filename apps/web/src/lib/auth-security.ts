import { timingSafeEqual } from "node:crypto";

export function csrfTokensMatch(cookieToken?: string, headerToken?: string | null): boolean {
  if (!cookieToken || !headerToken) return false;
  const left = Buffer.from(cookieToken);
  const right = Buffer.from(headerToken);
  return left.length === right.length && timingSafeEqual(left, right);
}

export function sessionCookieOptions(expires: Date, secure: boolean) {
  return { httpOnly: true, sameSite: "strict" as const, secure, path: "/", expires };
}

export function csrfCookieOptions(expires: Date, secure: boolean) {
  return { httpOnly: false, sameSite: "strict" as const, secure, path: "/", expires };
}

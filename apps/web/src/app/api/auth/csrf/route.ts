import { randomBytes } from "node:crypto";
import { cookies } from "next/headers";
import { CSRF_COOKIE, secureCookie } from "@/lib/server-auth";
import { csrfCookieOptions } from "@/lib/auth-security";

export async function GET() {
  const store = await cookies();
  if (!store.get(CSRF_COOKIE)) store.set(CSRF_COOKIE, randomBytes(32).toString("base64url"), csrfCookieOptions(new Date(Date.now() + 86400000), secureCookie()));
  return new Response(null, { status: 204 });
}

import { NextResponse } from "next/server";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession, secureCookie, SESSION_COOKIE } from "@/lib/server-auth";

export async function POST(request: Request) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  try {
    const coreResponse = await fetch(`${CORE_SERVICE_URL}/v1/integrations/spotify/authorization`, { method: "POST", headers: { Authorization: `Bearer ${auth.token}` } });
    const response = NextResponse.json(await coreResponse.json().catch(() => ({})), { status: coreResponse.status });
    if (coreResponse.ok) {
      // Upgrade sessions created before OAuth support from SameSite=Strict. The
      // existing backend token still controls the real expiry and validity.
      response.cookies.set(SESSION_COOKIE, auth.token, {
        httpOnly: true, sameSite: "lax", secure: secureCookie(), path: "/",
      });
    }
    return response;
  }
  catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

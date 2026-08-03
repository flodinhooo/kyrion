import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { setAuthCookies } from "../session-cookie";

export async function POST(request: Request) {
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/auth/password`, {
      method: "POST",
      headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body), cache: "no-store",
    });
    const value: unknown = await response.json().catch(() => ({}));
    if (!response.ok) return Response.json(value, { status: response.status });
    const session = value as { sessionToken?: unknown; expiresAt?: unknown };
    if (typeof session.sessionToken !== "string" || typeof session.expiresAt !== "string") {
      return Response.json({ code: "AUTH_SERVICE_INVALID_RESPONSE" }, { status: 502 });
    }
    await setAuthCookies(session.sessionToken, session.expiresAt);
    return Response.json({ changed: true });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

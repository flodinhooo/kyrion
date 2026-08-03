import { clearAuthCookies } from "../session-cookie";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function POST(request: Request) {
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    await fetch(`${CORE_SERVICE_URL}/v1/auth/logout`, {
      method: "POST", headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
  } finally {
    await clearAuthCookies();
  }
  return new Response(null, { status: 204 });
}

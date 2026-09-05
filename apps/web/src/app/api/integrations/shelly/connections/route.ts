import { isConnection } from "@/features/integrations/contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function POST(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/shelly/connections`, {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify(body), cache: "no-store",
    });
    const value: unknown = await response.json();
    if (!response.ok) {
      const code = value && typeof value === "object" && "code" in value && typeof value.code === "string"
        ? value.code : "CORE_INVALID_RESPONSE";
      return Response.json({ code }, { status: response.status });
    }
    return isConnection(value) ? Response.json(value, { status: 201 })
      : Response.json({ code: "CORE_INVALID_RESPONSE" }, { status: 502 });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

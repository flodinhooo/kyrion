import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

export async function GET(_request: Request, context: RouteContext<"/api/device-commands/[id]">) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  const { id } = await context.params;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/device-commands/${id}`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    return Response.json(await response.json().catch(() => ({})), { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

import { isGatewayNodeList } from "@/features/gateways/contracts";
import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/gateways`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    const value: unknown = await response.json().catch(() => null);
    return response.ok && isGatewayNodeList(value)
      ? Response.json(value, { headers: { "Cache-Control": "no-store" } })
      : Response.json(value ?? { code: "CORE_UNAVAILABLE" }, { status: response.status });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

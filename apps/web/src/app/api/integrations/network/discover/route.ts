import { isNetworkDeviceList } from "@/features/integrations/network-contracts";
import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

export async function POST(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/network/discover`, {
      method: "POST", headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    const value: unknown = await response.json();
    if (!response.ok) return Response.json({ code: "NETWORK_DISCOVERY_UNAVAILABLE" }, { status: response.status });
    return isNetworkDeviceList(value)
      ? Response.json(value, { headers: { "Cache-Control": "no-store" } })
      : Response.json({ code: "CORE_INVALID_RESPONSE" }, { status: 502 });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

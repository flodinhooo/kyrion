import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";
import { isConversationList } from "@/features/conversations/contracts";

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/conversations`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    const value: unknown = await response.json();
    return response.ok && isConversationList(value)
      ? Response.json(value, { headers: { "Cache-Control": "no-store" } })
      : Response.json({ code: "CORE_INVALID_RESPONSE" }, { status: 502 });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

import { isActivityResponse } from "@/features/activity/contracts";
import { requireApiSession } from "@/lib/server-auth";

const CORE_SERVICE_URL = process.env.CORE_SERVICE_URL ?? "http://127.0.0.1:8080";

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/activity?limit=50`, {
      headers: { Authorization: `Bearer ${auth.token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(2_500),
    });
    const activity: unknown = await response.json();
    if (!response.ok || !isActivityResponse(activity)) throw new Error("Invalid activity response");

    return Response.json(activity, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

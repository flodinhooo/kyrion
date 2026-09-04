import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

export async function GET(request: Request) {
  const incoming = new URL(request.url);
  const destination = new URL("/plugins/spotify", incoming.origin);
  const auth = await requireApiSession();
  if (auth instanceof Response) { destination.searchParams.set("spotify", "session"); return Response.redirect(destination); }
  const code = incoming.searchParams.get("code"); const state = incoming.searchParams.get("state");
  if (!code || !state || incoming.searchParams.has("error")) { destination.searchParams.set("spotify", "denied"); return Response.redirect(destination); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/spotify/authorization/complete`, {
      method: "POST", headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" }, body: JSON.stringify({ code, state }),
    });
    destination.searchParams.set("spotify", response.ok ? "connected" : "failed");
  } catch { destination.searchParams.set("spotify", "failed"); }
  return Response.redirect(destination);
}

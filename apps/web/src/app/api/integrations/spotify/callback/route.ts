import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";
import { localhostCallbackRelay, oauthRedirect } from "@/features/spotify/oauth-callback";

export async function GET(request: Request) {
  const incoming = new URL(request.url);
  const configuredPublicUrl = process.env.KYRION_PUBLIC_URL;
  const relay = localhostCallbackRelay(incoming, configuredPublicUrl, request.headers.get("host"));
  if (relay) return oauthRedirect(relay);
  let publicOrigin = incoming.origin;
  if (configuredPublicUrl) {
    try {
      const configured = new URL(configuredPublicUrl);
      if (configured.protocol === "https:" || configured.protocol === "http:") publicOrigin = configured.origin;
    } catch {
      // Keep the request origin as a development fallback for invalid configuration.
    }
  }
  const destination = new URL("/plugins/spotify", publicOrigin);
  const auth = await requireApiSession();
  if (auth instanceof Response) { destination.searchParams.set("spotify", "session"); return oauthRedirect(destination); }
  const code = incoming.searchParams.get("code"); const state = incoming.searchParams.get("state");
  if (!code || !state || incoming.searchParams.has("error")) { destination.searchParams.set("spotify", "denied"); return oauthRedirect(destination); }
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/spotify/authorization/complete`, {
      method: "POST", headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" }, body: JSON.stringify({ code, state }),
    });
    destination.searchParams.set("spotify", response.ok ? "connected" : "failed");
  } catch { destination.searchParams.set("spotify", "failed"); }
  return oauthRedirect(destination);
}

import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";
import { isSpotifyPlaylists } from "@/features/spotify/contracts";

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/spotify/playlists`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store", signal: AbortSignal.timeout(15000),
    });
    const value: unknown = await response.json();
    if (!response.ok) return Response.json(value, { status: response.status });
    if (!isSpotifyPlaylists(value)) return Response.json({ code: "SPOTIFY_INVALID_RESPONSE" }, { status: 502 });
    return Response.json(value);
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

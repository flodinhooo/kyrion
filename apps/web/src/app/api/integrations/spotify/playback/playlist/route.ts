import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { isSpotifyPlaylistCommand } from "@/features/spotify/contracts";

export async function PUT(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  if (!isSpotifyPlaylistCommand(body)) return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/spotify/playback/playlist`, {
      method: "PUT", headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body), signal: AbortSignal.timeout(15000),
    });
    return response.ok ? new Response(null, { status: 204 }) : Response.json(await response.json(), { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { isSpotifyPlaybackCommand } from "@/features/spotify/contracts";

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/spotify/playback`, {
      headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    return Response.json(await response.json(), { status: response.status });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

export async function PUT(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "INVALID_REQUEST" }, { status: 400 }); }
  if (!isSpotifyPlaybackCommand(body)) return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/spotify/playback`, {
      method: "PUT", headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return response.ok ? new Response(null, { status: 204 }) : Response.json(await response.json(), { status: response.status });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

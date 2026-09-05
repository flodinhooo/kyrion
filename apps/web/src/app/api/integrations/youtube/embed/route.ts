import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { isYouTubeEmbed, isYouTubeRequest } from "@/features/youtube/contracts";

export async function POST(request: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ code: "YOUTUBE_INVALID_LINK" }, { status: 400 }); }
  if (!isYouTubeRequest(body)) return Response.json({ code: "YOUTUBE_INVALID_LINK" }, { status: 400 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/integrations/youtube/embed`, {
      method: "POST", headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body), signal: AbortSignal.timeout(10000),
    });
    const value: unknown = await response.json();
    if (!response.ok) return Response.json(value, { status: response.status });
    if (!isYouTubeEmbed(value)) return Response.json({ code: "YOUTUBE_INVALID_RESPONSE" }, { status: 502 });
    return Response.json(value);
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

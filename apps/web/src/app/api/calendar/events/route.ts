import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { normalizeGoogleEvents, normalizeLocalEvents } from "@/features/calendar/calendar-model";

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const headers = { Authorization: `Bearer ${auth.token}` };
    const [localResponse, googleResponse] = await Promise.all([
      fetch(`${CORE_SERVICE_URL}/v1/calendar/events`, { headers }),
      fetch(`${CORE_SERVICE_URL}/v1/integrations/google/calendar/events`, { headers }),
    ]);
    const localValue: unknown = await localResponse.json().catch(() => null);
    if (!localResponse.ok) return Response.json(localValue ?? { code: "CORE_UNAVAILABLE" }, { status: localResponse.status });
    const googleValue: unknown = googleResponse.ok ? await googleResponse.json().catch(() => null) : null;
    return Response.json({ items: [...normalizeLocalEvents(localValue), ...normalizeGoogleEvents(googleValue)] });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}
export async function POST(request:Request) { const auth=await requireApiSession(); if(auth instanceof Response)return auth; if(!(await csrfIsValid(request)))return Response.json({code:"CSRF_INVALID"},{status:403}); try{const r=await fetch(`${CORE_SERVICE_URL}/v1/calendar/events`,{method:"POST",headers:{Authorization:`Bearer ${auth.token}`,"Content-Type":"application/json"},body:await request.text()});return Response.json(await r.json(),{status:r.status});}catch{return Response.json({code:"CORE_UNAVAILABLE"},{status:503});} }

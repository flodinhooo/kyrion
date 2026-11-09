import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";
import { isCalendarEvent, normalizeGoogleEvents, normalizeLocalEvents, normalizeHouseholdEvents } from "@/features/calendar/calendar-model";
import { ownedCopyLinks, confirmedOwnedCopies } from "@/features/calendar/owned-copy-presentation";

export async function GET(request?: Request) {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  try {
    const search = request ? new URL(request.url).searchParams : new URLSearchParams();
    const query = new URLSearchParams();
    for (const key of ["calendarId", "start", "end"]) { const value = search.get(key); if (value) query.set(key, value); }
    const headers = { Authorization: `Bearer ${auth.token}` };
    const householdQuery = new URLSearchParams();
    for (const key of ["start", "end"]) { const value = search.get(key); if (value) householdQuery.set(key, value); }
    const [localResponse, googleResponse, householdResponse] = await Promise.all([
      fetch(`${CORE_SERVICE_URL}/v1/calendar/events`, { headers, cache: "no-store", signal: AbortSignal.timeout(10_000) }),
      fetch(`${CORE_SERVICE_URL}/v1/integrations/google/calendar/events${query.size ? `?${query}` : ""}`, { headers, cache: "no-store", signal: AbortSignal.timeout(10_000) }).catch(() => null),
      fetch(`${CORE_SERVICE_URL}/v1/calendar/household-events${householdQuery.size ? `?${householdQuery}` : ""}`, { headers, cache: "no-store", signal: AbortSignal.timeout(10_000) }).catch(() => null),
    ]);
    const localValue: unknown = await localResponse.json().catch(() => null);
    if (!localResponse.ok) return Response.json(localValue ?? { code: "CORE_UNAVAILABLE" }, { status: localResponse.status });
    const googleValue: unknown = googleResponse ? await googleResponse.json().catch(() => null) : null;
    const googleValid = !!googleValue && typeof googleValue === "object" && "items" in googleValue && Array.isArray(googleValue.items);
    const googleReady = googleResponse?.ok && googleValid;
    const googleCode = googleValue && typeof googleValue === "object" && "code" in googleValue && typeof googleValue.code === "string" ? googleValue.code : "GOOGLE_UNAVAILABLE";
    const local = normalizeLocalEvents(localValue);
    if (!(Array.isArray(localValue) || (!!localValue && typeof localValue === "object" && "items" in localValue && Array.isArray(localValue.items))) || !local.every(isCalendarEvent)) return Response.json({ code: "CORE_INVALID_RESPONSE" }, { status: 502 });
    const remote = googleReady ? normalizeGoogleEvents(googleValue) : [];
    const householdValue: unknown = householdResponse ? await householdResponse.json().catch(() => null) : null;
    const household = householdResponse?.ok ? normalizeHouseholdEvents(householdValue) : null;
    const selected = search.get("calendarId") ?? "primary";
    const linked = new Set(local.filter(event => event.googleCalendarId === selected && event.googleEventId).map(event => `google:${event.googleEventId}`));
    let copyStatus = "not_needed";
    let copies = new Set<string>();
    if (household?.length && remote.length) {
      const copyQuery = new URLSearchParams(householdQuery); copyQuery.set("calendarId", selected);
      const response = await fetch(`${CORE_SERVICE_URL}/v1/calendar/household-copy-links?${copyQuery}`, {
        headers, cache: "no-store", signal: AbortSignal.timeout(2_000),
      }).catch(() => null);
      const links = response?.ok ? ownedCopyLinks(await response.json().catch(() => null)) : null;
      copyStatus = links === null ? "unavailable" : "ready";
      copies = confirmedOwnedCopies(googleValue, household, links);
    }
    return Response.json({
      personalItems: remote,
      items: [...local, ...remote.filter(event => !linked.has(event.id) && !copies.has(event.id)), ...(household ?? [])],
      google: { status: googleReady ? "ready" : googleCode === "GOOGLE_DISCONNECTED" ? "disconnected" : "error", code: googleReady ? null : googleCode },
      household: { status: household !== null ? "ready" : "error" },
      copies: { status: copyStatus },
    }, { headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}
export async function POST(request:Request) { const auth=await requireApiSession(); if(auth instanceof Response)return auth; if(!(await csrfIsValid(request)))return Response.json({code:"CSRF_INVALID"},{status:403}); try{const r=await fetch(`${CORE_SERVICE_URL}/v1/calendar/events`,{method:"POST",headers:{Authorization:`Bearer ${auth.token}`,"Content-Type":"application/json"},body:await request.text()});return Response.json(await r.json(),{status:r.status});}catch{return Response.json({code:"CORE_UNAVAILABLE"},{status:503});} }

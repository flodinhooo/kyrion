import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";
async function secure(request:Request){const auth=await requireApiSession();if(auth instanceof Response)return auth;if(!(await csrfIsValid(request)))return Response.json({code:"CSRF_INVALID"},{status:403});return auth;}
export async function PUT(request:Request,context:RouteContext<"/api/calendar/events/[id]">){const auth=await secure(request);if(auth instanceof Response)return auth;const{id}=await context.params;try{const r=await fetch(`${CORE_SERVICE_URL}/v1/calendar/events/${id}`,{method:"PUT",headers:{Authorization:`Bearer ${auth.token}`,"Content-Type":"application/json"},body:await request.text()});return Response.json(await r.json(),{status:r.status});}catch{return Response.json({code:"CORE_UNAVAILABLE"},{status:503});}}

export async function DELETE(request: Request, context: RouteContext<"/api/calendar/events/[id]">) {
  const auth = await secure(request);
  if (auth instanceof Response) return auth;
  const {id} = await context.params;
  const revision = new URL(request.url).searchParams.get("revision");
  const query = revision === null ? "" : `?${new URLSearchParams({revision})}`;
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/calendar/events/${encodeURIComponent(id)}${query}`, {
      method: "DELETE", headers: {Authorization: `Bearer ${auth.token}`},
    });
    // Core's Unit-returning controller can acknowledge deletion with empty 200.
    // Never parse a successful empty body and turn completed work into a 503.
    if (response.ok) return new Response(null, {status: 204});
    return Response.json(await response.json().catch(() => ({code: "CORE_INVALID_RESPONSE"})), {
      status: response.status,
    });
  } catch {
    return Response.json({code: "CORE_UNAVAILABLE"}, {status: 503});
  }
}

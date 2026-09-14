import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";
type Context = { params: Promise<{ id: string }> };
async function auth(request: Request) { const a=await requireApiSession(); if(a instanceof Response)return a; if(!(await csrfIsValid(request)))return Response.json({code:"CSRF_INVALID"},{status:403}); return a; }
async function forward(request:Request, context:Context, method:string){const a=await auth(request);if(a instanceof Response)return a;const {id}=await context.params;const r=await fetch(`${CORE_SERVICE_URL}/v1/rbac/roles/${id}`,{method,headers:{Authorization:`Bearer ${a.token}`,"Content-Type":"application/json"},body:method === "DELETE" ? undefined : await request.text()});return new Response(await r.text(),{status:r.status,headers:{"content-type":"application/json"}})}
export const PUT=(r:Request,c:Context)=>forward(r,c,"PUT"); export const DELETE=(r:Request,c:Context)=>forward(r,c,"DELETE");

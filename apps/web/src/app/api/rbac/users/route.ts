import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";
export async function GET(){const a=await requireApiSession();if(a instanceof Response)return a;const r=await fetch(`${CORE_SERVICE_URL}/v1/rbac/users`,{headers:{Authorization:`Bearer ${a.token}`},cache:"no-store"});return new Response(await r.text(),{status:r.status,headers:{"content-type":"application/json"}});}

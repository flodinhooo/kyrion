import { requireApiSession } from "@/lib/server-auth";
export async function GET() {
  const auth = await requireApiSession();
  return auth instanceof Response ? auth : Response.json({ user: auth.user }, { headers: { "Cache-Control": "no-store" } });
}

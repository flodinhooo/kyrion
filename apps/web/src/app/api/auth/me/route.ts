import { currentUser } from "@/lib/server-auth";
export async function GET() {
  const user = await currentUser();
  return user ? Response.json({ user }) : Response.json({ code: "UNAUTHENTICATED" }, { status: 401 });
}

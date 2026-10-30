import { spaceProxy } from "@/features/spaces/proxy";

const allowed: Record<string, readonly string[]> = {
  email: ["GET", "POST"], "email/verify": ["POST"], business: ["GET", "PUT"],
  "business/challenge": ["POST"], "business/verify": ["POST"], "business/suspend": ["POST"],
};
async function forward(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const path = (await params).path.join("/");
  if (!allowed[path]?.includes(request.method)) return Response.json({ code: "NOT_FOUND" }, { status: 404 });
  return spaceProxy(request, `/v1/identity/${path}`);
}
export const GET = forward;
export const POST = forward;
export const PUT = forward;

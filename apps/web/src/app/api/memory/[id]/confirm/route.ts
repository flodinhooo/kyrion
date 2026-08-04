import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

type Context = { params: Promise<{ id: string }> };

export async function POST(request: Request, context: Context) {
  const auth = await requireApiSession(); if (auth instanceof Response) return auth;
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const { id } = await context.params;
  const resolution = new URL(request.url).searchParams.get("resolution") === "replace" ? "replace" : "keep";
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/memory/${id}/confirm?resolution=${resolution}`, {
      method: "POST", headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    return Response.json(await response.json(), { status: response.status });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

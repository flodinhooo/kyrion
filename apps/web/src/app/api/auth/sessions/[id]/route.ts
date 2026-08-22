import { CORE_SERVICE_URL, csrfIsValid, requireApiSession } from "@/lib/server-auth";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export async function DELETE(request: Request, context: { params: Promise<{ id: string }> }) {
  if (!(await csrfIsValid(request))) return Response.json({ code: "CSRF_INVALID" }, { status: 403 });
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;
  const { id } = await context.params;
  if (!UUID.test(id)) return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/auth/sessions/${id}`, {
      method: "DELETE", headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store",
    });
    if (response.status === 204) return new Response(null, { status: 204 });
    const value: unknown = await response.json().catch(() => ({}));
    return Response.json(value, { status: response.status });
  } catch {
    return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 });
  }
}

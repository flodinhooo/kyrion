import { spaceProxy } from "@/features/spaces/proxy";
export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
  return spaceProxy(request, `/v1/space/invitations/${id}`);
}

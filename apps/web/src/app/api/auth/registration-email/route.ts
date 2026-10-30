import { CORE_SERVICE_URL } from "@/lib/server-auth";

export async function POST(request: Request) {
  try {
    const raw = await request.text();
    if (raw.length > 4096) return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || !("email" in value) || typeof value.email !== "string"
      || !("invitationCode" in value) || typeof value.invitationCode !== "string") return Response.json({ code: "INVALID_REQUEST" }, { status: 400 });
    await fetch(`${CORE_SERVICE_URL}/v1/auth/registration-email`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: value.email, invitationCode: value.invitationCode }),
      cache: "no-store", signal: AbortSignal.timeout(15_000),
    });
    return Response.json({ accepted: true }, { status: 202, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ code: "CORE_UNAVAILABLE" }, { status: 503 }); }
}

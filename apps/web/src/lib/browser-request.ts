// Never retry commands automatically: after a lost response their outcome is unknown.
export async function browserRequest(input: string, init: RequestInit = {}): Promise<Response> {
  try {
    return await fetch(input, { ...init, signal: init.signal ?? AbortSignal.timeout(15_000) });
  } catch {
    return Response.json({ code: "REQUEST_OUTCOME_UNKNOWN" }, { status: 503 });
  }
}

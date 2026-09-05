const callbackPath = "/api/integrations/spotify/callback";

/** Return to the configured localhost session without copying authentication cookies. */
export function localhostCallbackRelay(incoming: URL, publicUrl?: string, requestHost?: string | null): URL | null {
  if (!publicUrl) return null;
  let target: URL;
  try { target = new URL(publicUrl); } catch { return null; }
  // Next dev can normalize request.url to localhost; retain the actual Host.
  const port = incoming.port ? `:${incoming.port}` : "";
  const host = requestHost ?? incoming.host;
  if (incoming.protocol !== "http:" || ![`127.0.0.1${port}`, `[::1]${port}`].includes(host)
    || incoming.pathname !== callbackPath || target.protocol !== "http:"
    || target.hostname !== "localhost" || target.port !== incoming.port
    || target.username || target.password) return null;

  const relay = new URL(callbackPath, target.origin);
  for (const key of ["code", "state", "error"] as const) {
    const value = incoming.searchParams.get(key);
    if (value !== null) relay.searchParams.set(key, value);
  }
  return relay;
}

export function oauthRedirect(destination: URL): Response {
  return new Response(null, {
    status: 303,
    headers: {
      Location: destination.toString(),
      "Cache-Control": "no-store",
      "Referrer-Policy": "no-referrer",
    },
  });
}

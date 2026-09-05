import { describe, expect, it } from "vitest";
import { localhostCallbackRelay, oauthRedirect } from "./oauth-callback";

const path = "/api/integrations/spotify/callback";

describe("local Spotify callback", () => {
  it("relays only OAuth parameters to the configured localhost callback", () => {
    const result = localhostCallbackRelay(new URL(`http://127.0.0.1:3000${path}?code=a%2Bb&state=s&next=https://evil.example&token=secret`), "http://localhost:3000");
    expect(result?.toString()).toBe(`http://localhost:3000${path}?code=a%2Bb&state=s`);
  });

  it("relays denial and IPv6 loopback callbacks", () => {
    expect(localhostCallbackRelay(new URL(`http://[::1]:3000${path}?error=access_denied&state=s`), "http://localhost:3000")?.search).toBe("?state=s&error=access_denied");
  });

  it("uses the actual loopback Host when Next dev normalizes the request URL", () => {
    const incoming = new URL(`http://localhost:3000${path}?code=c&state=s`);
    expect(localhostCallbackRelay(incoming, "http://localhost:3000", "127.0.0.1:3000")?.search).toBe("?code=c&state=s");
    expect(localhostCallbackRelay(incoming, "http://localhost:3000", "localhost:3000")).toBeNull();
    expect(localhostCallbackRelay(incoming, "http://localhost:3000", "127.0.0.1:4000")).toBeNull();
  });

  it("never loops or relays production and remote hosts", () => {
    for (const origin of ["http://localhost:3000", "https://kyrion-node.local", "http://evil.example:3000", "http://127.0.0.1.evil.example:3000"]) {
      expect(localhostCallbackRelay(new URL(`${origin}${path}`), "http://localhost:3000")).toBeNull();
    }
  });

  it("requires explicit same-port localhost configuration and the callback path", () => {
    const incoming = new URL(`http://127.0.0.1:3000${path}`);
    for (const target of [undefined, "invalid", "http://localhost:4000", "https://localhost:3000", "http://evil.example:3000", "http://user@localhost:3000"]) {
      expect(localhostCallbackRelay(incoming, target)).toBeNull();
    }
    expect(localhostCallbackRelay(new URL("http://127.0.0.1:3000/login"), "http://localhost:3000")).toBeNull();
  });

  it("does not cache OAuth redirects or leak parameters through referrers", () => {
    const response = oauthRedirect(new URL(`http://localhost:3000${path}?code=c&state=s`));
    expect(response.status).toBe(303);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    expect(response.headers.has("set-cookie")).toBe(false);
  });
});

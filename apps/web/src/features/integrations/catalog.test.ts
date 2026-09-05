import { afterEach, describe, expect, it, vi } from "vitest";
import { loadIntegrationCatalog } from "./catalog";

afterEach(() => vi.unstubAllGlobals());

describe("integration catalog status", () => {
  it("isolates failed status reads instead of discarding healthy integrations", async () => {
    vi.stubGlobal("fetch", vi.fn(async (path: string) => {
      if (path === "/api/gateways") throw new Error("offline");
      if (path.endsWith("/spotify")) return Response.json({ configured: true, connected: true, accountName: "Owner" });
      return Response.json([]);
    }));
    const result = await loadIntegrationCatalog(new AbortController().signal);
    expect(result.nanoleaf).toEqual({ status: "available", count: 0 });
    expect(result.zigbee.status).toBe("error");
    expect(result.spotify.status).toBe("connected");
  });

  it("rejects invalid responses and reports missing server configuration", async () => {
    vi.stubGlobal("fetch", vi.fn(async (path: string) => Response.json(path.endsWith("/spotify")
      ? { configured: false, connected: false, accountName: null } : { items: [] })));
    const result = await loadIntegrationCatalog(new AbortController().signal);
    expect(result.nanoleaf.status).toBe("error");
    expect(result.zigbee.status).toBe("error");
    expect(result.spotify.status).toBe("server_configuration");
  });

  it("labels saved connections as configured rather than online", async () => {
    vi.stubGlobal("fetch", vi.fn(async (path: string) => {
      if (path.endsWith("/connections")) return Response.json([{ id: "saved", provider: "nanoleaf", displayName: "Panels", endpointHost: "local", createdAt: "2026-09-05", roomId: null, deviceClass: "light" }]);
      return new Response(null, { status: 503 });
    }));
    expect((await loadIntegrationCatalog(new AbortController().signal)).nanoleaf).toEqual({ status: "configured", count: 1 });
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { browserRequest } from "./browser-request";

afterEach(() => vi.unstubAllGlobals());
describe("bounded browser requests", () => {
  it("reports a lost command response without retrying or claiming success", async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError("offline")); vi.stubGlobal("fetch", fetcher);
    const response = await browserRequest("/api/device-commands", { method: "POST" });
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ code: "REQUEST_OUTCOME_UNKNOWN" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
  });
  it("preserves the authority's response and caller cancellation", async () => {
    const response = Response.json({ code: "FORBIDDEN" }, { status: 403 });
    const fetcher = vi.fn().mockResolvedValue(response); vi.stubGlobal("fetch", fetcher);
    const controller = new AbortController();
    expect(await browserRequest("/api/devices", { signal: controller.signal })).toBe(response);
    expect(fetcher.mock.calls[0][1].signal).toBe(controller.signal);
  });
});

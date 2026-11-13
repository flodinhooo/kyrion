import { afterEach, describe, expect, it, vi } from "vitest";
import { runDeviceCommand } from "./device-command";

afterEach(() => vi.useRealTimers());
describe("one explicit device write", () => {
  for (const failure of ["network", "http", "json", "schema"] as const) {
    it(`restores controls and announces ${failure} failure without retry`, async () => {
      const pending = vi.fn(),
        failed = vi.fn(),
        accept = vi.fn(() => false);
      const send = vi.fn(async () => {
        if (failure === "network") throw new TypeError("offline");
        return new Response(failure === "json" ? "invalid json" : "{}", {
          status: failure === "http" ? 503 : 200,
        });
      });
      await runDeviceCommand(send, accept, pending, failed);
      expect(send).toHaveBeenCalledTimes(1);
      expect(pending.mock.calls).toEqual([[true], [false]]);
      expect(failed.mock.calls).toEqual([[false], [true]]);
      if (failure === "http") expect(accept).not.toHaveBeenCalled();
    });
  }
  it("bounds a stalled request and permits a later explicit attempt", async () => {
    vi.useFakeTimers();
    const pending = vi.fn(),
      failed = vi.fn();
    const send = vi.fn(
      (signal: AbortSignal) =>
        new Promise<Response>((_, reject) =>
          signal.addEventListener(
            "abort",
            () => reject(new DOMException("timeout", "AbortError")),
            { once: true },
          ),
        ),
    );
    const result = runDeviceCommand(send, () => true, pending, failed);
    await vi.advanceTimersByTimeAsync(15_000);
    await result;
    expect(send).toHaveBeenCalledTimes(1);
    expect(pending).toHaveBeenLastCalledWith(false);
    expect(failed).toHaveBeenLastCalledWith(true);
    const success = vi.fn(async () => Response.json({ on: true }));
    const accept = vi.fn(() => true);
    await runDeviceCommand(success, accept, pending, failed);
    expect(success).toHaveBeenCalledTimes(1);
    expect(accept).toHaveBeenCalledWith({ on: true });
    expect(failed).toHaveBeenLastCalledWith(false);
    expect(vi.getTimerCount()).toBe(0);
  });
});

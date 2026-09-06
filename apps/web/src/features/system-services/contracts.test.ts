import { describe, expect, it } from "vitest";
import { isSystemServicesStatus } from "./contracts";

describe("system service status contract", () => {
  it("accepts a bounded service observation", () => {
    expect(isSystemServicesStatus({
      observedAt: "2026-08-22T19:30:00.000Z",
      services: [{
        id: "core", displayName: "Kyrion Core", host: "127.0.0.1", port: 8080,
        status: "healthy", detail: null, latencyMs: 12, source: "probe",
      }],
    })).toBe(true);
  });

  it("rejects invalid ports and status values", () => {
    expect(isSystemServicesStatus({
      observedAt: "2026-08-22T19:30:00.000Z",
      services: [{
        id: "core", displayName: "Kyrion Core", host: "127.0.0.1", port: 99_999,
        status: "running", detail: null, latencyMs: 12, source: "probe",
      }],
    })).toBe(false);
  });
});

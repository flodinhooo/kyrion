import { describe, expect, it } from "vitest";
import { gatewayDiagnostic, probeDiagnostic } from "./diagnostics";

describe("truthful service diagnostics", () => {
  it("never promotes old child observations when the gateway is offline or unknown", () => {
    expect(gatewayDiagnostic("offline", "ready")).toEqual({ status: "unknown", reason: "dependency_offline" });
    expect(gatewayDiagnostic("unknown", "ready").status).toBe("unknown");
    expect(gatewayDiagnostic("online", "ready").status).toBe("healthy");
    expect(gatewayDiagnostic("online", "not_configured").reason).toBe("configuration_missing");
    expect(gatewayDiagnostic("online", "unavailable").status).toBe("offline");
    expect(gatewayDiagnostic("degraded", "degraded").status).toBe("degraded");
  });
  it("validates probe bodies and distinguishes authentication errors", () => {
    expect(probeDiagnostic("core", 200, { status: "UP" }).status).toBe("healthy");
    expect(probeDiagnostic("core", 200, { status: "DOWN" }).status).toBe("degraded");
    expect(probeDiagnostic("core", 200, {}).reason).toBe("invalid_response");
    expect(probeDiagnostic("ai", 401, {}).reason).toBe("authentication_failed");
    expect(probeDiagnostic("ai", 200, { status: "ok" }).status).toBe("healthy");
    expect(probeDiagnostic("ollama", 200, { version: "1" }).status).toBe("healthy");
  });
});

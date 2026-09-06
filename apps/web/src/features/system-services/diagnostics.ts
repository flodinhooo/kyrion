import type { GatewayServiceStatus } from "@/features/gateways/contracts";
import type { DiagnosticReason, SystemServiceStatus } from "./contracts";

export function gatewayDiagnostic(parent: string, child: GatewayServiceStatus): { status: SystemServiceStatus; reason: DiagnosticReason | null } {
  if (parent === "offline") return { status: "unknown", reason: "dependency_offline" };
  if (parent === "unknown") return { status: "unknown", reason: "stale_observation" };
  if (child === "not_configured") return { status: "unknown", reason: "configuration_missing" };
  if (child === "unavailable") return { status: "offline", reason: "dependency_unreachable" };
  if (child === "ready") return { status: "healthy", reason: null };
  return { status: child, reason: child === "unknown" ? "no_observation" : "dependency_error" };
}

export function probeDiagnostic(id: string, httpStatus: number, body: unknown): { status: SystemServiceStatus; reason: DiagnosticReason | null } {
  if (httpStatus === 401 || httpStatus === 403) return { status: "degraded", reason: "authentication_failed" };
  if (httpStatus < 200 || httpStatus >= 300) return { status: "degraded", reason: "dependency_error" };
  if (!body || typeof body !== "object") return { status: "unknown", reason: "invalid_response" };
  if (id === "ollama" && "version" in body && typeof body.version === "string" && body.version.length > 0) return { status: "healthy", reason: null };
  if ("status" in body && (id === "core" ? body.status === "UP" : body.status === "ok" || body.status === "ready")) return { status: "healthy", reason: null };
  if ("status" in body && ["DOWN", "OUT_OF_SERVICE", "degraded", "unavailable", "error"].includes(String(body.status))) return { status: "degraded", reason: "dependency_error" };
  return { status: "unknown", reason: "invalid_response" };
}

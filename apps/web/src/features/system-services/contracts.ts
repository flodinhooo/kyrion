export type SystemServiceStatus = "healthy" | "offline" | "degraded" | "unknown";
export const diagnosticReasons = ["configuration_missing", "configuration_invalid", "authentication_failed", "dependency_unreachable", "dependency_error", "invalid_response", "stale_observation", "no_observation", "dependency_offline"] as const;
export type DiagnosticReason = typeof diagnosticReasons[number];

export type SystemService = {
  id: string;
  displayName: string;
  host: string;
  port: number | null;
  status: SystemServiceStatus;
  detail: string | null;
  latencyMs: number | null;
  source: "web" | "probe" | "gateway" | "core";
  reason?: DiagnosticReason | null;
  lastError?: DiagnosticReason | null;
  lastSuccessAt?: string | null;
  correlationId?: string | null;
};

export type SystemServicesStatus = {
  observedAt: string;
  services: SystemService[];
};

const statuses = new Set<SystemServiceStatus>(["healthy", "offline", "degraded", "unknown"]);
const sources = new Set<SystemService["source"]>(["web", "probe", "gateway", "core"]);

export function isSystemServicesStatus(value: unknown): value is SystemServicesStatus {
  if (!value || typeof value !== "object") return false;
  const result = value as Partial<SystemServicesStatus>;
  return typeof result.observedAt === "string" && !Number.isNaN(Date.parse(result.observedAt))
    && Array.isArray(result.services) && result.services.length <= 50
    && result.services.every((service) => !!service && typeof service.id === "string"
      && typeof service.displayName === "string" && typeof service.host === "string"
      && (service.port === null || (Number.isInteger(service.port) && service.port > 0 && service.port <= 65_535))
      && statuses.has(service.status) && (service.detail === null || (typeof service.detail === "string" && Number.isFinite(Date.parse(service.detail))))
      && (service.latencyMs === null || (typeof service.latencyMs === "number" && service.latencyMs >= 0))
      && (service.reason == null || diagnosticReasons.some((reason) => reason === service.reason))
      && (service.lastError == null || diagnosticReasons.some((reason) => reason === service.lastError))
      && (service.lastSuccessAt == null || (typeof service.lastSuccessAt === "string" && Number.isFinite(Date.parse(service.lastSuccessAt))))
      && (service.correlationId == null || typeof service.correlationId === "string")
      && sources.has(service.source));
}

export type SystemServiceStatus = "ready" | "unavailable" | "degraded" | "unknown";

export type SystemService = {
  id: string;
  displayName: string;
  host: string;
  port: number | null;
  status: SystemServiceStatus;
  detail: string | null;
  latencyMs: number | null;
  source: "web" | "probe" | "gateway";
};

export type SystemServicesStatus = {
  observedAt: string;
  services: SystemService[];
};

const statuses = new Set<SystemServiceStatus>(["ready", "unavailable", "degraded", "unknown"]);
const sources = new Set<SystemService["source"]>(["web", "probe", "gateway"]);

export function isSystemServicesStatus(value: unknown): value is SystemServicesStatus {
  if (!value || typeof value !== "object") return false;
  const result = value as Partial<SystemServicesStatus>;
  return typeof result.observedAt === "string" && !Number.isNaN(Date.parse(result.observedAt))
    && Array.isArray(result.services) && result.services.length <= 50
    && result.services.every((service) => !!service && typeof service.id === "string"
      && typeof service.displayName === "string" && typeof service.host === "string"
      && (service.port === null || (Number.isInteger(service.port) && service.port > 0 && service.port <= 65_535))
      && statuses.has(service.status) && (service.detail === null || typeof service.detail === "string")
      && (service.latencyMs === null || (typeof service.latencyMs === "number" && service.latencyMs >= 0))
      && sources.has(service.source));
}

import { isGatewayNodeList } from "@/features/gateways/contracts";
import type { SystemService, SystemServicesStatus } from "@/features/system-services/contracts";
import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";
import { gatewayDiagnostic, probeDiagnostic } from "@/features/system-services/diagnostics";
import { diagnosticReasons } from "@/features/system-services/contracts";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000";
const OLLAMA_SERVICE_URL = process.env.OLLAMA_SERVICE_URL ?? "http://127.0.0.1:11434";
const STT_SERVICE_URL = process.env.STT_SERVICE_URL ?? "http://127.0.0.1:8040";
const TIMEOUT_MS = 2_500;

type Probe = { id: string; displayName: string; url: string; healthPath: string };

const probes: Probe[] = [
  { id: "core", displayName: "Kyrion Core", url: CORE_SERVICE_URL, healthPath: "/actuator/health" },
  { id: "ai", displayName: "Kyrion AI", url: AI_SERVICE_URL, healthPath: "/health" },
  { id: "ollama", displayName: "Ollama", url: OLLAMA_SERVICE_URL, healthPath: "/api/version" },
  { id: "stt", displayName: "Parakeet STT", url: STT_SERVICE_URL, healthPath: "/health" },
];

export async function GET() {
  const auth = await requireApiSession();
  if (auth instanceof Response) return auth;

  const [local, gatewayServices, imported, database] = await Promise.all([
    Promise.all(probes.map(probe)), readGatewayServices(auth.token),
    coreDiagnostic(auth.token, "home-assistant", "Home Assistant", "/v1/integrations/home-assistant"),
    coreDiagnostic(auth.token, "postgresql", "PostgreSQL", "/v1/integrations/platform-diagnostics/database"),
  ]);
  const status: SystemServicesStatus = {
    observedAt: new Date().toISOString(),
    services: [
      { id: "web", displayName: "Kyrion Web", host: "", port: null, status: "healthy", detail: new Date().toISOString(), latencyMs: null, source: "web" },
      ...local,
      ...gatewayServices,
      imported, database,
      ...missingGatewayObservations(gatewayServices),
    ],
  };
  return Response.json(status, { headers: { "Cache-Control": "no-store" } });
}

function missingGatewayObservations(services: SystemService[]): SystemService[] {
  return [
    { id: "gateway", name: "Gateway Agent", present: services.some((service) => service.source === "gateway") },
    { id: "voice", name: "Voice Satellite", present: services.some((service) => service.id.endsWith(":voice")) },
    { id: "zigbee", name: "Zigbee2MQTT", present: services.some((service) => service.id.endsWith(":zigbee")) },
    { id: "spotify-receiver", name: "Spotify Receiver", present: services.some((service) => service.id.endsWith(":spotify-receiver") || service.id.endsWith(":spotify")) },
  ].filter((item) => !item.present).map((item) => ({ id: item.id, displayName: item.name, host: "", port: null,
    status: "unknown", reason: "no_observation", detail: null, latencyMs: null, source: "gateway" }));
}

async function probe(item: Probe): Promise<SystemService> {
  let parsed: URL;
  try {
    parsed = new URL(item.url);
    if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("Invalid protocol");
  } catch {
    return { id: item.id, displayName: item.displayName, host: "", port: null, status: "unknown",
      detail: null, latencyMs: null, source: "probe", reason: "configuration_invalid" };
  }
  const started = performance.now();
  try {
    const response = await fetch(`${item.url}${item.healthPath}`, {
      cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const diagnostic = probeDiagnostic(item.id, response.status, await response.json().catch(() => null));
    const observedAt = new Date().toISOString();
    return { ...service(item, parsed, diagnostic.status, Math.round(performance.now() - started)), ...diagnostic,
      detail: observedAt, lastSuccessAt: diagnostic.status === "healthy" ? observedAt : null };
  } catch {
    return { ...service(item, parsed, "offline", null), reason: "dependency_unreachable" };
  }
}

function service(item: Probe, url: URL, status: SystemService["status"], latencyMs: number | null): SystemService {
  return {
    id: item.id, displayName: item.displayName, host: url.hostname,
    port: url.port ? Number(url.port) : url.protocol === "https:" ? 443 : 80,
    status, detail: null, latencyMs, source: "probe",
  };
}

async function readGatewayServices(token: string): Promise<SystemService[]> {
  const failed: SystemService = { id: "gateway", displayName: "Gateway Agent", host: "", port: null,
    status: "unknown", reason: "dependency_unreachable", detail: null, latencyMs: null, source: "gateway" };
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/gateways`, {
      headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const value: unknown = await response.json().catch(() => null);
    if (!response.ok || !isGatewayNodeList(value)) return [{ ...failed, reason: response.status === 401 || response.status === 403 ? "authentication_failed" : "invalid_response" }];
    return value.flatMap((node) => {
      const nodeStatus: SystemService["status"] = node.availability === "online" ? "healthy" : node.availability;
      const gateway: SystemService = {
        id: `gateway:${node.id}`, displayName: node.displayName, host: node.hostname, port: null,
        status: nodeStatus, detail: node.lastSeenAt, latencyMs: null, source: "gateway",
      };
      const children = (node.health?.services ?? []).map((child): SystemService => ({
        id: `gateway:${node.id}:${child.id}`,
        displayName: child.id,
        host: node.hostname,
        port: null,
        ...gatewayDiagnostic(node.availability, child.status),
        detail: node.lastSeenAt,
        latencyMs: null,
        source: "gateway",
      }));
      return [gateway, ...children];
    });
  } catch {
    return [failed];
  }
}

async function coreDiagnostic(token: string, id: string, displayName: string, path: string): Promise<SystemService> {
  const base: SystemService = { id, displayName, host: "", port: null, status: "unknown", detail: null, latencyMs: null, source: "core", reason: "no_observation" };
  try {
    const response = await fetch(`${CORE_SERVICE_URL}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS) });
    const value: unknown = await response.json();
    if (!response.ok || !value || typeof value !== "object" || !("status" in value) ||
      !["healthy", "offline", "degraded", "unknown"].includes(String(value.status))) return { ...base, reason: "invalid_response" };
    const reason = "reason" in value ? diagnosticReasons.find((reason) => reason === value.reason) ?? null : null;
    const date = (key: string): string | null => key in value && typeof Reflect.get(value, key) === "string" && Number.isFinite(Date.parse(Reflect.get(value, key))) ? Reflect.get(value, key) : null;
    return { ...base, status: value.status as SystemService["status"], reason,
      lastError: "lastError" in value ? diagnosticReasons.find((reason) => reason === value.lastError) ?? null : null,
      detail: date("lastAttemptAt") ?? date("observedAt"), lastSuccessAt: date("lastSuccessAt"),
      correlationId: "correlationId" in value && typeof value.correlationId === "string" ? value.correlationId : null };
  } catch { return { ...base, reason: "dependency_unreachable" }; }
}

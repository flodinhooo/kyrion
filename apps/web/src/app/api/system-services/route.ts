import { isGatewayNodeList } from "@/features/gateways/contracts";
import type { SystemService, SystemServicesStatus } from "@/features/system-services/contracts";
import { CORE_SERVICE_URL, requireApiSession } from "@/lib/server-auth";

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

  const local = await Promise.all(probes.map(probe));
  const gatewayServices = await readGatewayServices(auth.token);
  const status: SystemServicesStatus = {
    observedAt: new Date().toISOString(),
    services: [
      { id: "web", displayName: "Kyrion Web", host: "localhost", port: 3000, status: "ready", detail: null, latencyMs: null, source: "web" },
      ...local,
      ...gatewayServices,
    ],
  };
  return Response.json(status, { headers: { "Cache-Control": "no-store" } });
}

async function probe(item: Probe): Promise<SystemService> {
  const parsed = new URL(item.url);
  const started = performance.now();
  try {
    const response = await fetch(`${item.url}${item.healthPath}`, {
      cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    return service(item, parsed, response.ok ? "ready" : "degraded", Math.round(performance.now() - started));
  } catch {
    return service(item, parsed, "unavailable", null);
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
  try {
    const response = await fetch(`${CORE_SERVICE_URL}/v1/gateways`, {
      headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const value: unknown = await response.json().catch(() => null);
    if (!response.ok || !isGatewayNodeList(value)) return [];
    return value.flatMap((node) => {
      const nodeStatus: SystemService["status"] = node.availability === "online" ? "ready"
        : node.availability === "offline" ? "unavailable" : node.availability;
      const gateway: SystemService = {
        id: `gateway:${node.id}`, displayName: node.displayName, host: node.hostname, port: null,
        status: nodeStatus, detail: node.lastSeenAt, latencyMs: null, source: "gateway",
      };
      const children = (node.health?.services ?? []).map((child): SystemService => ({
        id: `gateway:${node.id}:${child.id}`,
        displayName: child.id,
        host: node.hostname,
        port: null,
        status: child.status,
        detail: node.lastSeenAt,
        latencyMs: null,
        source: "gateway",
      }));
      return [gateway, ...children];
    });
  } catch {
    return [];
  }
}

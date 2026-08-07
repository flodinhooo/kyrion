export type GatewayAvailability = "online" | "offline" | "degraded" | "unknown";
export type GatewayServiceStatus = "ready" | "unavailable" | "not_configured" | "degraded" | "unknown";
export type GatewayZigbeeDevice = {
  ieeeAddress: string; friendlyName: string; vendor: string; model: string;
  description: string; supported: boolean; on: boolean | null;
  brightness: number | null; linkquality: number | null;
  hue: number | null; saturation: number | null; colorTemperature: number | null;
};

export type GatewayHealth = {
  temperatureCelsius: number | null;
  throttled: boolean;
  memoryTotalBytes: number;
  memoryAvailableBytes: number;
  storageTotalBytes: number;
  storageAvailableBytes: number;
  ethernet: { present: boolean; connected: boolean };
  wifi: { present: boolean; connected: boolean };
  ipv6: boolean;
  bluetooth: boolean;
  systemState: "running" | "degraded" | "maintenance" | "unknown";
  adapters: Array<{
    id: string; protocol: "zigbee" | "thread"; vendor: string; model: string; serial: string; path: string;
  }>;
  zigbee: null | {
    permitJoin: boolean;
    channel: number;
    devices: GatewayZigbeeDevice[];
  };
  services: Array<{ id: string; status: GatewayServiceStatus }>;
};

export type GatewayNode = {
  id: string;
  displayName: string;
  hostname: string;
  availability: GatewayAvailability;
  agentVersion: string;
  osName: string;
  osVersion: string;
  architecture: string;
  lastSeenAt: string | null;
  health: GatewayHealth | null;
  createdAt: string;
};

export type GatewayEnrollment = { id: string; enrollmentToken: string; expiresAt: string };

const serviceStatuses = new Set<GatewayServiceStatus>([
  "ready", "unavailable", "not_configured", "degraded", "unknown",
]);

function isInterface(value: unknown): value is GatewayHealth["ethernet"] {
  if (!value || typeof value !== "object") return false;
  const item = value as { present?: unknown; connected?: unknown };
  return typeof item.present === "boolean" && typeof item.connected === "boolean";
}

function isHealth(value: unknown): value is GatewayHealth {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<GatewayHealth>;
  return (item.temperatureCelsius === null || typeof item.temperatureCelsius === "number")
    && typeof item.throttled === "boolean"
    && typeof item.memoryTotalBytes === "number" && typeof item.memoryAvailableBytes === "number"
    && typeof item.storageTotalBytes === "number" && typeof item.storageAvailableBytes === "number"
    && isInterface(item.ethernet) && isInterface(item.wifi)
    && typeof item.ipv6 === "boolean" && typeof item.bluetooth === "boolean"
    && (item.systemState === "running" || item.systemState === "degraded"
      || item.systemState === "maintenance" || item.systemState === "unknown")
    && Array.isArray(item.adapters) && item.adapters.length <= 16
    && item.adapters.every((adapter) => !!adapter && typeof adapter.id === "string"
      && (adapter.protocol === "zigbee" || adapter.protocol === "thread")
      && typeof adapter.vendor === "string" && typeof adapter.model === "string"
      && typeof adapter.serial === "string" && typeof adapter.path === "string"
      && adapter.path.startsWith("/dev/serial/by-id/"))
    && (item.zigbee === null || (!!item.zigbee && typeof item.zigbee.permitJoin === "boolean"
      && typeof item.zigbee.channel === "number" && isGatewayZigbeeDeviceList(item.zigbee.devices)))
    && Array.isArray(item.services) && item.services.length <= 32
    && item.services.every((service) => !!service && typeof service.id === "string"
      && serviceStatuses.has(service.status));
}

export function isGatewayZigbeeDeviceList(value: unknown): value is GatewayZigbeeDevice[] {
  return Array.isArray(value) && value.length <= 100 && value.every((device) =>
    !!device && typeof device.ieeeAddress === "string" && typeof device.friendlyName === "string"
    && typeof device.vendor === "string" && typeof device.model === "string"
    && typeof device.description === "string" && typeof device.supported === "boolean"
    && (device.on === null || typeof device.on === "boolean")
    && (device.brightness === null || typeof device.brightness === "number")
    && (device.hue === null || typeof device.hue === "number")
    && (device.saturation === null || typeof device.saturation === "number")
    && (device.colorTemperature === null || typeof device.colorTemperature === "number")
    && (device.linkquality === null || typeof device.linkquality === "number"));
}

export function isGatewayNode(value: unknown): value is GatewayNode {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<GatewayNode>;
  return typeof item.id === "string" && typeof item.displayName === "string"
    && typeof item.hostname === "string"
    && (item.availability === "online" || item.availability === "offline"
      || item.availability === "degraded" || item.availability === "unknown")
    && typeof item.agentVersion === "string" && typeof item.osName === "string"
    && typeof item.osVersion === "string" && typeof item.architecture === "string"
    && (item.lastSeenAt === null || typeof item.lastSeenAt === "string")
    && (item.health === null || isHealth(item.health)) && typeof item.createdAt === "string";
}

export function isGatewayNodeList(value: unknown): value is GatewayNode[] {
  return Array.isArray(value) && value.length <= 50 && value.every(isGatewayNode);
}

export function isGatewayEnrollment(value: unknown): value is GatewayEnrollment {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<GatewayEnrollment>;
  return typeof item.id === "string" && typeof item.enrollmentToken === "string"
    && item.enrollmentToken.length <= 200 && typeof item.expiresAt === "string";
}

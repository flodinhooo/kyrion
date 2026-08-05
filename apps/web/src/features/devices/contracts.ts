export type DeviceAvailability = "online" | "offline" | "degraded" | "unknown";

export type RuntimeDevice = {
  id: string;
  provider: string;
  displayName: string;
  room: { id: string; name: string } | null;
  capabilities: Array<{ id: string }>;
  availability: DeviceAvailability;
  observedAt: string | null;
};

export function isRuntimeDevice(value: unknown): value is RuntimeDevice {
  if (!value || typeof value !== "object") return false;
  const device = value as Partial<RuntimeDevice>;
  const room = device.room as Partial<NonNullable<RuntimeDevice["room"]>> | null | undefined;
  return typeof device.id === "string" && typeof device.provider === "string"
    && typeof device.displayName === "string"
    && (room === null || (!!room && typeof room.id === "string" && typeof room.name === "string"))
    && Array.isArray(device.capabilities)
    && device.capabilities.every((capability) => !!capability && typeof capability.id === "string")
    && (device.availability === "online" || device.availability === "offline"
      || device.availability === "degraded" || device.availability === "unknown")
    && (device.observedAt === null || typeof device.observedAt === "string");
}

export function isRuntimeDeviceList(value: unknown): value is RuntimeDevice[] {
  return Array.isArray(value) && value.length <= 250 && value.every(isRuntimeDevice);
}

export type DeviceCommandResult = {
  capability: string;
  roomName: string;
  requested: number;
  succeeded: number;
  failed: number;
  outcomes: Array<{ deviceId: string; displayName: string; status: "succeeded" | "unavailable" | "failed" }>;
  correlationId: string;
};

export function isDeviceCommandResult(value: unknown): value is DeviceCommandResult {
  if (!value || typeof value !== "object") return false;
  const result = value as Partial<DeviceCommandResult>;
  return typeof result.capability === "string" && typeof result.roomName === "string"
    && Number.isInteger(result.requested) && Number.isInteger(result.succeeded)
    && Number.isInteger(result.failed) && Array.isArray(result.outcomes)
    && result.outcomes.every((outcome) => !!outcome && typeof outcome.deviceId === "string"
      && typeof outcome.displayName === "string"
      && (outcome.status === "succeeded" || outcome.status === "unavailable" || outcome.status === "failed"))
    && typeof result.correlationId === "string";
}

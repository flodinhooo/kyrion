export type DeviceAvailability = "online" | "offline" | "degraded" | "unknown";
export type DeviceClass = "light" | "switch" | "sensor" | "other";

export type RuntimeDevice = {
  id: string;
  provider: string;
  deviceClass: DeviceClass;
  displayName: string;
  hardwareName: string;
  room: { id: string; name: string; roomType: string } | null;
  capabilities: Array<{ id: string }>;
  availability: DeviceAvailability;
  observedAt: string | null;
  state: { on: boolean | null; brightness: number | null; hue: number | null; saturation: number | null; colorTemperature: number | null; occupancy: boolean | null; battery: number | null; illuminance: number | null; action: string | null } | null;
};

export function isRuntimeDevice(value: unknown): value is RuntimeDevice {
  if (!value || typeof value !== "object") return false;
  const device = value as Partial<RuntimeDevice>;
  const room = device.room as Partial<NonNullable<RuntimeDevice["room"]>> | null | undefined;
  return typeof device.id === "string" && typeof device.provider === "string"
    && (device.deviceClass === "light" || device.deviceClass === "switch" || device.deviceClass === "sensor" || device.deviceClass === "other")
    && typeof device.displayName === "string"
    && typeof device.hardwareName === "string"
    && (room === null || (!!room && typeof room.id === "string" && typeof room.name === "string" && typeof room.roomType === "string"))
    && Array.isArray(device.capabilities)
    && device.capabilities.every((capability) => !!capability && typeof capability.id === "string")
    && (device.availability === "online" || device.availability === "offline"
      || device.availability === "degraded" || device.availability === "unknown")
    && (device.observedAt === null || typeof device.observedAt === "string")
    && (device.state === null || (!!device.state && (device.state.on === null || typeof device.state.on === "boolean")
      && (device.state.brightness === null || typeof device.state.brightness === "number")
      && (device.state.hue === null || typeof device.state.hue === "number")
      && (device.state.saturation === null || typeof device.state.saturation === "number")
      && (device.state.colorTemperature === null || typeof device.state.colorTemperature === "number")
      && (device.state.occupancy === null || typeof device.state.occupancy === "boolean")
      && (device.state.battery === null || typeof device.state.battery === "number")
      && (device.state.illuminance === null || typeof device.state.illuminance === "number")
      && (device.state.action === null || typeof device.state.action === "string")));
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

export type AsyncDeviceCommand = { commandId: string; deviceId: string; status: "pending" };
export type DeviceCommandStatus = { id: string; status: "pending" | "running" | "succeeded" | "failed"; errorCode: string | null };

export function isAsyncDeviceCommand(value: unknown): value is AsyncDeviceCommand {
  if (!value || typeof value !== "object") return false;
  const command = value as Partial<AsyncDeviceCommand>;
  return typeof command.commandId === "string" && typeof command.deviceId === "string" && command.status === "pending";
}

export function isDeviceCommandStatus(value: unknown): value is DeviceCommandStatus {
  if (!value || typeof value !== "object") return false;
  const command = value as Partial<DeviceCommandStatus>;
  return typeof command.id === "string" && ["pending", "running", "succeeded", "failed"].includes(command.status ?? "")
    && (command.errorCode === null || typeof command.errorCode === "string");
}

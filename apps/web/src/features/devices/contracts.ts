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
  state: { on: boolean | null; brightness: number | null; hue: number | null; saturation: number | null; colorTemperature: number | null; occupancy: boolean | null; battery: number | null; illuminance: number | null; action: string | null; illumination: "dim" | "bright" | null; temperatureCelsius?: number | null; relativeHumidity?: number | null; measuredAt?: string | null } | null;
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
      && (device.state.action === null || typeof device.state.action === "string")
      && optionalMeasurement(device.state.temperatureCelsius, -100, 150)
      && optionalMeasurement(device.state.relativeHumidity, 0, 100)
      && (device.state.measuredAt == null || (typeof device.state.measuredAt === "string" && Number.isFinite(Date.parse(device.state.measuredAt))))
      && (device.state.illumination === null || device.state.illumination === "dim" || device.state.illumination === "bright")));
}

function optionalMeasurement(value: unknown, min: number, max: number): boolean {
  return value == null || (typeof value === "number" && Number.isFinite(value) && value >= min && value <= max);
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

export type ButtonGesture = "single" | "double" | "long";
export type ButtonAction = "toggle" | "turn_on" | "turn_off";
export type ButtonBinding = { gesture: ButtonGesture; targetDeviceId: string | null; targetRoomId: string | null; action: ButtonAction };

export function isButtonBindingList(value: unknown): value is ButtonBinding[] {
  return Array.isArray(value) && value.length <= 3 && value.every((item) => {
    if (!item || typeof item !== "object") return false;
    const binding = item as Partial<ButtonBinding>;
    return (binding.gesture === "single" || binding.gesture === "double" || binding.gesture === "long")
      && ((typeof binding.targetDeviceId === "string" && binding.targetRoomId === null)
        || (binding.targetDeviceId === null && typeof binding.targetRoomId === "string"))
      && (binding.action === "toggle" || binding.action === "turn_on" || binding.action === "turn_off");
  });
}

export type MotionEvent = { id: string; detected: boolean; occurredAt: string };

export function isMotionEventList(value: unknown): value is MotionEvent[] {
  return Array.isArray(value) && value.length <= 12 && value.every((item) => {
    if (!item || typeof item !== "object") return false;
    const event = item as Partial<MotionEvent>;
    return typeof event.id === "string" && typeof event.detected === "boolean"
      && typeof event.occurredAt === "string";
  });
}

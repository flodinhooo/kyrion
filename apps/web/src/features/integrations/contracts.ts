export type IntegrationConnection = { id: string; provider: "nanoleaf"; displayName: string; endpointHost: string; createdAt: string; roomId: string | null };
export type NanoleafState = { name: string; model: string | null; serialNumber: string | null; on: boolean; brightness: number | null; hue: number | null; saturation: number | null; colorTemperature: number | null; colorMode: string | null };
export type DiscoveredNanoleaf = { name: string; host: string; port: number };
export type NanoleafScenes = { active: string | null; items: string[]; previews: Record<string, string[]> };

export function isConnection(value: unknown): value is IntegrationConnection {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<IntegrationConnection>;
  return typeof item.id === "string" && item.provider === "nanoleaf" && typeof item.displayName === "string"
    && typeof item.endpointHost === "string" && typeof item.createdAt === "string" && (item.roomId === null || typeof item.roomId === "string");
}
export function isConnectionList(value: unknown): value is IntegrationConnection[] { return Array.isArray(value) && value.every(isConnection); }
export function isNanoleafState(value: unknown): value is NanoleafState {
  if (!value || typeof value !== "object") return false;
  const state = value as Partial<NanoleafState>;
  return typeof state.name === "string" && typeof state.on === "boolean"
    && (state.model === null || typeof state.model === "string")
    && (state.serialNumber === null || typeof state.serialNumber === "string")
    && (state.brightness === null || typeof state.brightness === "number")
    && (state.hue === null || typeof state.hue === "number") && (state.saturation === null || typeof state.saturation === "number")
    && (state.colorTemperature === null || typeof state.colorTemperature === "number") && (state.colorMode === null || typeof state.colorMode === "string");
}
export function isDiscoveredNanoleafList(value: unknown): value is DiscoveredNanoleaf[] {
  return Array.isArray(value) && value.every((item) => !!item && typeof item === "object"
    && typeof (item as DiscoveredNanoleaf).name === "string" && typeof (item as DiscoveredNanoleaf).host === "string"
    && (item as DiscoveredNanoleaf).port === 16021);
}
export function isNanoleafScenes(value: unknown): value is NanoleafScenes {
  if (!value || typeof value !== "object") return false;
  const scenes = value as Partial<NanoleafScenes>;
  return (scenes.active === null || typeof scenes.active === "string")
    && Array.isArray(scenes.items) && scenes.items.every((item) => typeof item === "string")
    && !!scenes.previews && typeof scenes.previews === "object" && Object.values(scenes.previews).every((colors) => Array.isArray(colors) && colors.every((color) => typeof color === "string"));
}

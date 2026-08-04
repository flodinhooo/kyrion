export type IntegrationConnection = { id: string; provider: "nanoleaf"; displayName: string; endpointHost: string; createdAt: string };
export type NanoleafState = { name: string; model: string | null; serialNumber: string | null; on: boolean; brightness: number | null };
export type DiscoveredNanoleaf = { name: string; host: string; port: number };

export function isConnection(value: unknown): value is IntegrationConnection {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<IntegrationConnection>;
  return typeof item.id === "string" && item.provider === "nanoleaf" && typeof item.displayName === "string"
    && typeof item.endpointHost === "string" && typeof item.createdAt === "string";
}
export function isConnectionList(value: unknown): value is IntegrationConnection[] { return Array.isArray(value) && value.every(isConnection); }
export function isNanoleafState(value: unknown): value is NanoleafState {
  if (!value || typeof value !== "object") return false;
  const state = value as Partial<NanoleafState>;
  return typeof state.name === "string" && typeof state.on === "boolean"
    && (state.model === null || typeof state.model === "string")
    && (state.serialNumber === null || typeof state.serialNumber === "string")
    && (state.brightness === null || typeof state.brightness === "number");
}
export function isDiscoveredNanoleafList(value: unknown): value is DiscoveredNanoleaf[] {
  return Array.isArray(value) && value.every((item) => !!item && typeof item === "object"
    && typeof (item as DiscoveredNanoleaf).name === "string" && typeof (item as DiscoveredNanoleaf).host === "string"
    && (item as DiscoveredNanoleaf).port === 16021);
}

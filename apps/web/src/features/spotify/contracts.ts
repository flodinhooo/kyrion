export type SpotifyStatus = { configured: boolean; connected: boolean; accountName: string | null };
export type SpotifyDevice = { id: string; name: string; type: string; active: boolean; restricted: boolean; volumePercent: number | null; supportsVolume: boolean };

export function isSpotifyStatus(value: unknown): value is SpotifyStatus {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<SpotifyStatus>;
  return typeof item.configured === "boolean" && typeof item.connected === "boolean"
    && (item.accountName === null || typeof item.accountName === "string");
}

export function isSpotifyDeviceList(value: unknown): value is SpotifyDevice[] {
  return Array.isArray(value) && value.every((entry) => {
    if (!entry || typeof entry !== "object") return false;
    const item = entry as Partial<SpotifyDevice>;
    return typeof item.id === "string" && typeof item.name === "string" && typeof item.type === "string"
      && typeof item.active === "boolean" && typeof item.restricted === "boolean"
      && (item.volumePercent === null || typeof item.volumePercent === "number") && typeof item.supportsVolume === "boolean";
  });
}

export type SpotifyStatus = { configured: boolean; connected: boolean; accountName: string | null };
export type SpotifyDevice = { id: string; name: string; type: string; active: boolean; restricted: boolean; volumePercent: number | null; supportsVolume: boolean };

export type SpotifyPlayback = {
  playing: boolean; title: string | null; artist: string | null; imageUrl: string | null;
  trackUrl: string | null; progressMs: number; durationMs: number; deviceId: string | null; disallowed: string[];
};
export type SpotifyPlaybackCommand = {
  action: "RESUME" | "PAUSE" | "NEXT" | "PREVIOUS"; deviceId: string;
} | { action: "VOLUME"; deviceId: string; volumePercent: number };

function safeUrl(value: unknown, host: string): boolean {
  if (value === null) return true;
  if (typeof value !== "string") return false;
  try { const url = new URL(value); return url.protocol === "https:" && url.hostname === host && !url.username && !url.password; }
  catch { return false; }
}

export function isSpotifyPlayback(value: unknown): value is SpotifyPlayback {
  if (!value || typeof value !== "object") return false;
  return "playing" in value && typeof value.playing === "boolean"
    && "title" in value && (value.title === null || typeof value.title === "string")
    && "artist" in value && (value.artist === null || typeof value.artist === "string")
    && "deviceId" in value && (value.deviceId === null || typeof value.deviceId === "string")
    && "imageUrl" in value && safeUrl(value.imageUrl, "i.scdn.co")
    && "trackUrl" in value && safeUrl(value.trackUrl, "open.spotify.com")
    && "progressMs" in value && typeof value.progressMs === "number" && Number.isInteger(value.progressMs) && value.progressMs >= 0
    && "durationMs" in value && typeof value.durationMs === "number" && Number.isInteger(value.durationMs) && value.durationMs >= 0
    && "disallowed" in value && Array.isArray(value.disallowed) && value.disallowed.every((entry) => typeof entry === "string");
}

export function isSpotifyPlaybackCommand(value: unknown): value is SpotifyPlaybackCommand {
  if (!value || typeof value !== "object" || !("deviceId" in value) || typeof value.deviceId !== "string"
    || !value.deviceId.trim() || value.deviceId.length > 200 || !("action" in value)) return false;
  if (value.action === "VOLUME") return "volumePercent" in value && typeof value.volumePercent === "number"
    && Number.isInteger(value.volumePercent) && value.volumePercent >= 0 && value.volumePercent <= 100;
  return ["RESUME", "PAUSE", "NEXT", "PREVIOUS"].some((action) => value.action === action) && !("volumePercent" in value);
}

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

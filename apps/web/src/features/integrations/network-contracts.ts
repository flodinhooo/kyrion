export type NetworkDevice = { provider: "nanoleaf" | "shelly"; name: string; host: string; port: number };

export function isNetworkDeviceList(value: unknown): value is NetworkDevice[] {
  return Array.isArray(value) && value.length <= 100 && value.every((item: unknown) => {
    if (!item || typeof item !== "object") return false;
    return "provider" in item && "name" in item && "host" in item && "port" in item
      && ((item.provider === "nanoleaf" && item.port === 16021) || (item.provider === "shelly" && item.port === 80))
      && typeof item.name === "string" && item.name.length <= 160
      && typeof item.host === "string" && /^(?:\d{1,3}\.){3}\d{1,3}$/.test(item.host);
  });
}

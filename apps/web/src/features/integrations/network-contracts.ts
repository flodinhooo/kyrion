export type NetworkDevice = { provider: "nanoleaf" | "shelly" | "network"; name: string; host: string; port: number; connected?: boolean };

export function isNetworkDeviceList(value: unknown): value is NetworkDevice[] {
  return Array.isArray(value) && value.length <= 512 && value.every((item: unknown) => {
    if (!item || typeof item !== "object") return false;
    return "provider" in item && "name" in item && "host" in item && "port" in item
      && (item.provider === "nanoleaf" || item.provider === "shelly" || item.provider === "network")
      && typeof item.port === "number" && Number.isInteger(item.port) && item.port >= 0 && item.port <= 65535
      && typeof item.name === "string" && item.name.length <= 160
      && (!("connected" in item) || typeof item.connected === "boolean")
      && typeof item.host === "string" && /^(?:\d{1,3}\.){3}\d{1,3}$/.test(item.host)
      && item.host.split(".").every((octet) => Number(octet) <= 255);
  });
}

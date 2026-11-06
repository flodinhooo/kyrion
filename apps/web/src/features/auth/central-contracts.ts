export type CentralStatus = { linked: boolean; issuer?: string };
export type CentralDevice = { userCode: string; verificationUri: string; expiresAt: string; interval: number };

export function isCentralStatus(value: unknown): value is CentralStatus {
  return !!value && typeof value === "object" && "linked" in value && typeof value.linked === "boolean"
    && (!("issuer" in value) || typeof value.issuer === "string");
}

export function isCentralDevice(value: unknown): value is CentralDevice {
  if (!value || typeof value !== "object") return false;
  const device = value as Partial<CentralDevice>;
  if (typeof device.userCode !== "string" || device.userCode.length > 128
    || typeof device.verificationUri !== "string" || typeof device.expiresAt !== "string"
    || !Number.isFinite(Date.parse(device.expiresAt)) || typeof device.interval !== "number"
    || !Number.isFinite(device.interval) || device.interval < 1 || device.interval > 300) return false;
  try {
    const url = new URL(device.verificationUri);
    return !url.username && !url.password && !url.hash
      && (url.protocol === "https:" || (url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)));
  } catch { return false; }
}

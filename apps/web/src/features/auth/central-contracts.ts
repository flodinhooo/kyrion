export type CentralStatus = {
  linked: boolean;
  issuer?: string;
  linkedAt?: string;
  account?: { email: string | null; displayName: string | null } | null;
  directoryState?: "confirmed" | "pending" | "not_available"
};
export type CentralDevice = { userCode: string; verificationUri: string; expiresAt: string; interval: number };

export function isCentralStatus(value: unknown): value is CentralStatus {
  return !!value && typeof value === "object" && "linked" in value && typeof value.linked === "boolean"
    && (!("issuer" in value) || value.issuer === null || typeof value.issuer === "string")
    && (!("linkedAt" in value) || value.linkedAt === null || (typeof value.linkedAt === "string" && Number.isFinite(Date.parse(value.linkedAt))))
    && (!("directoryState" in value) || value.directoryState === null || ["confirmed", "pending", "not_available"].includes(String(value.directoryState)))
    && (!("account" in value) || value.account === null || (typeof value.account === "object" && value.account !== null && "email" in value.account && (value.account.email === null || typeof value.account.email === "string") && "displayName" in value.account && (value.account.displayName === null || typeof value.account.displayName === "string")));
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

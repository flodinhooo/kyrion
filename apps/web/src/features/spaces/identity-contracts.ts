export type EmailIdentity = { email: string | null; pendingEmail: string | null; status: "MISSING" | "PENDING" | "VERIFIED" | "LOCALLY_ATTESTED"; smtpAvailable: boolean };
export type BusinessPolicy = { mode: "OFF" | "STRICT"; recoveryConfigured: boolean; domains: { domain: string; allowed: boolean; status: "VERIFIED" | "PENDING"; verifiedUntil: string | null }[] };
export type DnsChallenge = { name: string; value: string; expiresAt: string };
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object";
const nullableString = (value: unknown) => value === null || typeof value === "string";
export function isEmailIdentity(value: unknown): value is EmailIdentity {
  return object(value) && nullableString(value.email) && nullableString(value.pendingEmail) && typeof value.smtpAvailable === "boolean"
    && ["MISSING", "PENDING", "VERIFIED", "LOCALLY_ATTESTED"].includes(String(value.status));
}
export function isBusinessPolicy(value: unknown): value is BusinessPolicy {
  return object(value) && (value.mode === "OFF" || value.mode === "STRICT") && typeof value.recoveryConfigured === "boolean"
    && Array.isArray(value.domains) && value.domains.every((domain: unknown) => object(domain) && typeof domain.domain === "string"
      && typeof domain.allowed === "boolean" && (domain.status === "VERIFIED" || domain.status === "PENDING") && nullableString(domain.verifiedUntil));
}
export function isDnsChallenge(value: unknown): value is DnsChallenge {
  return object(value) && typeof value.name === "string" && typeof value.value === "string" && typeof value.expiresAt === "string"
    && Number.isFinite(Date.parse(value.expiresAt));
}

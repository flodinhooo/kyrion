export type AiPreferences = {
  chatProfileId: string | null; voiceProfileId: string | null; preferredProvider: string | null;
  localOnly: boolean; allowedCloudProviders: string[]; routingPreference: string;
  allowFallback: boolean; monthlyTokenLimit: number | null;
};
export type AiPolicy = {
  allowedProviders: string[]; allowCloud: boolean; allowedProfiles: string[]; allowUserSelection: boolean;
  cloudDataScope: string; priorities: string[]; taskProfiles: Record<string, string[]>;
  allowFallback: boolean; fallbackProfiles: string[]; monthlyTokenLimit: number | null;
  monthlyCostLimit: number | null; currency: string | null; maxRequestTokens: number; maxTimeoutSeconds: number;
};
export type AiSettings = { preferences: AiPreferences; policy: AiPolicy; canAdmin: boolean };
export type AiAccountingState = "pending" | "invoked" | "uncertain" | "estimated" | "reported" | "rejected";
export type AiCostBasis = "reservation" | "provider_usage_estimate" | "not_invoked";
export type AiUsage = {
  period: string; tokenLimit: number | null; costLimit: number | null; currency: string | null;
  chargedTokens: number; costsAreEstimates: boolean; rows: Array<{
    provider: string; profileId: string; modelId: string;
    requests: number; chargedTokens: number; inputTokens: number | null; outputTokens: number | null;
    estimatedCost: number | null; currency: string | null; pending: number;
    accountingState?: AiAccountingState; unknownCosts?: number; costBasis?: AiCostBasis;
  }>;
  openAttempts?: Array<{
    id: string; period: string; provider: string; profileId: string; state: AiAccountingState;
    chargedTokens: number; estimatedCost: number | null; currency: string | null; errorCode: string | null;
  }>;
  openAttemptsTruncated?: boolean;
};

function object(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === "string");
const nullableString = (value: unknown) => value === null || typeof value === "string";
const nullableNumber = (value: unknown) => value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0);
const count = (value: unknown) => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const accountingState = (value: unknown): value is AiAccountingState =>
  ["pending", "invoked", "uncertain", "estimated", "reported", "rejected"].some(state => state === value);
const costBasis = (value: unknown): value is AiCostBasis =>
  ["reservation", "provider_usage_estimate", "not_invoked"].some(basis => basis === value);

export function isAiSettings(value: unknown): value is AiSettings {
  if (!object(value) || !object(value.preferences) || !object(value.policy) || typeof value.canAdmin !== "boolean") return false;
  const p = value.preferences, a = value.policy;
  return [p.chatProfileId, p.voiceProfileId, p.preferredProvider].every(nullableString)
    && typeof p.localOnly === "boolean" && strings(p.allowedCloudProviders) && typeof p.routingPreference === "string"
    && typeof p.allowFallback === "boolean" && nullableNumber(p.monthlyTokenLimit)
    && strings(a.allowedProviders) && typeof a.allowCloud === "boolean" && strings(a.allowedProfiles)
    && typeof a.allowUserSelection === "boolean" && a.cloudDataScope === "current_message" && strings(a.priorities)
    && object(a.taskProfiles) && Object.values(a.taskProfiles).every(strings) && typeof a.allowFallback === "boolean"
    && strings(a.fallbackProfiles) && nullableNumber(a.monthlyTokenLimit) && nullableNumber(a.monthlyCostLimit)
    && nullableString(a.currency) && typeof a.maxRequestTokens === "number" && typeof a.maxTimeoutSeconds === "number";
}

export function isAiUsage(value: unknown): value is AiUsage {
  return object(value) && typeof value.period === "string" && nullableNumber(value.tokenLimit) && nullableNumber(value.costLimit)
    && nullableString(value.currency) && typeof value.chargedTokens === "number" && typeof value.costsAreEstimates === "boolean"
    && Array.isArray(value.rows) && value.rows.every(row => object(row) && typeof row.provider === "string"
      && typeof row.profileId === "string" && typeof row.modelId === "string" && typeof row.requests === "number"
      && typeof row.chargedTokens === "number" && nullableNumber(row.inputTokens) && nullableNumber(row.outputTokens)
      && nullableNumber(row.estimatedCost) && nullableString(row.currency) && count(row.pending)
      && (row.accountingState === undefined || accountingState(row.accountingState))
      && (row.unknownCosts === undefined || count(row.unknownCosts))
      && (row.costBasis === undefined || costBasis(row.costBasis)))
    && (value.openAttemptsTruncated === undefined || typeof value.openAttemptsTruncated === "boolean")
    && (value.openAttempts === undefined || (Array.isArray(value.openAttempts) && value.openAttempts.length <= 100
      && value.openAttempts.every(row => object(row) && typeof row.id === "string" && typeof row.period === "string"
        && typeof row.provider === "string" && typeof row.profileId === "string" && accountingState(row.state)
        && count(row.chargedTokens) && nullableNumber(row.estimatedCost) && nullableString(row.currency) && nullableString(row.errorCode))));
}

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
export type AiUsage = {
  period: string; tokenLimit: number | null; costLimit: number | null; currency: string | null;
  chargedTokens: number; costsAreEstimates: boolean; rows: Array<{
    provider: string; profileId: string; modelId: string;
    requests: number; chargedTokens: number; inputTokens: number | null; outputTokens: number | null;
    estimatedCost: number | null; currency: string | null; pending: number
  }>
};

function object(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === "string");
const nullableString = (value: unknown) => value === null || typeof value === "string";
const nullableNumber = (value: unknown) => value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0);

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
      && nullableNumber(row.estimatedCost) && nullableString(row.currency) && typeof row.pending === "number");
}

export const retentionPeriods = ["keep_forever", "30_days", "90_days", "365_days", "3_years"] as const;
export type RetentionPeriod = typeof retentionPeriods[number];
export type RetentionPolicy = {
  conversations: RetentionPeriod; activity: RetentionPeriod; personalMemory: RetentionPeriod;
  updatedAt: string | null; enforcementActive: boolean; manualCleanupAvailable: boolean;
};
export type RetentionDomainPreview = { policy: RetentionPeriod; cutoff: string | null; records: number };
export type RetentionCleanupPreview = {
  generatedAt: string; conversations: RetentionDomainPreview; activity: RetentionDomainPreview; personalMemory: RetentionDomainPreview;
};
export function isRetentionPolicy(value: unknown): value is RetentionPolicy {
  if (!value || typeof value !== "object") return false;
  const policy = value as Partial<RetentionPolicy>;
  const valid = (item: unknown): item is RetentionPeriod => retentionPeriods.includes(item as RetentionPeriod);
  return valid(policy.conversations) && valid(policy.activity) && valid(policy.personalMemory)
    && (policy.updatedAt === null || typeof policy.updatedAt === "string") && policy.enforcementActive === false
    && policy.manualCleanupAvailable === true;
}
export function isRetentionCleanupPreview(value: unknown): value is RetentionCleanupPreview {
  if (!value || typeof value !== "object") return false;
  const preview = value as Partial<RetentionCleanupPreview>;
  const validDomain = (domain: unknown): domain is RetentionDomainPreview => {
    if (!domain || typeof domain !== "object") return false;
    const item = domain as Partial<RetentionDomainPreview>;
    return retentionPeriods.includes(item.policy as RetentionPeriod) && (item.cutoff === null || typeof item.cutoff === "string")
      && typeof item.records === "number" && Number.isInteger(item.records) && item.records >= 0;
  };
  return typeof preview.generatedAt === "string" && validDomain(preview.conversations)
    && validDomain(preview.activity) && validDomain(preview.personalMemory);
}

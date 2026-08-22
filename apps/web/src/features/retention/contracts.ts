export const retentionPeriods = ["keep_forever", "30_days", "90_days", "365_days", "3_years"] as const;
export type RetentionPeriod = typeof retentionPeriods[number];
export type RetentionPolicy = {
  conversations: RetentionPeriod; activity: RetentionPeriod; personalMemory: RetentionPeriod;
  updatedAt: string | null; enforcementActive: boolean;
};
export function isRetentionPolicy(value: unknown): value is RetentionPolicy {
  if (!value || typeof value !== "object") return false;
  const policy = value as Partial<RetentionPolicy>;
  const valid = (item: unknown): item is RetentionPeriod => retentionPeriods.includes(item as RetentionPeriod);
  return valid(policy.conversations) && valid(policy.activity) && valid(policy.personalMemory)
    && (policy.updatedAt === null || typeof policy.updatedAt === "string") && policy.enforcementActive === false;
}

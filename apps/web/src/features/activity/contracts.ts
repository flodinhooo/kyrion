export const activityCategories = ["SYSTEM", "CAPABILITY", "INTEGRATION", "AUTOMATION", "SECURITY"] as const;
export const activityStatuses = ["PROPOSED", "CONFIRMED", "SUCCEEDED", "FAILED", "DENIED"] as const;
export const activityActorTypes = ["SYSTEM", "USER", "AI", "INTEGRATION"] as const;

export type ActivityCategory = (typeof activityCategories)[number];
export type ActivityStatus = (typeof activityStatuses)[number];
export type ActivityActorType = (typeof activityActorTypes)[number];

export type ActivityEvent = {
  id: string;
  occurredAt: string;
  category: ActivityCategory;
  eventType: string;
  status: ActivityStatus;
  actorType: ActivityActorType;
  actorId: string | null;
  source: string;
  correlationId: string;
  summaryCode: string;
};

export type ActivityResponse = { items: ActivityEvent[] };

const isString = (value: unknown): value is string => typeof value === "string";

export function isActivityResponse(value: unknown): value is ActivityResponse {
  if (!value || typeof value !== "object" || !("items" in value) || !Array.isArray(value.items)) return false;

  return value.items.every((item) => {
    if (!item || typeof item !== "object") return false;
    const event = item as Record<string, unknown>;
    return isString(event.id)
      && isString(event.occurredAt)
      && activityCategories.includes(event.category as ActivityCategory)
      && isString(event.eventType)
      && activityStatuses.includes(event.status as ActivityStatus)
      && activityActorTypes.includes(event.actorType as ActivityActorType)
      && (event.actorId === null || isString(event.actorId))
      && isString(event.source)
      && isString(event.correlationId)
      && isString(event.summaryCode);
  });
}

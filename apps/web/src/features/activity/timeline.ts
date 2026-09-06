import type { ActivityEvent } from "./contracts";

export function executionDuration(events: ActivityEvent[], truncated = false): number | null {
  if (truncated) return null;
  const start = events.find((event) => event.eventType === "action.request.received" || event.eventType === "action.proposed");
  const end = events.findLast((event) => ["action.completed", "action.rejected", "action.confirmation_required"].includes(event.eventType))
    ?? (start?.eventType === "action.request.received" ? events.findLast((event) => event.eventType === "action.adapter.completed") : undefined);
  if (!start || !end) return null;
  const duration = Date.parse(end.occurredAt) - Date.parse(start.occurredAt);
  return Number.isFinite(duration) && duration >= 0 ? duration : null;
}

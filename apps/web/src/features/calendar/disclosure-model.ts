import { isCalendarEvent, type CalendarEvent } from "./calendar-model";
export type Visibility = "PRIVATE" | "AVAILABILITY" | "DETAILS";
export type DisclosureSetting = {
  id: string;
  calendarId: string;
  visibility: Visibility;
  revision: number;
  recipientIds?: string[]
};
export type SharedSource = { id: string; userId: string; username: string; visibility: Exclude<Visibility, "PRIVATE"> };
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const visibility = (value: unknown): value is Visibility => ["PRIVATE", "AVAILABILITY", "DETAILS"].includes(String(value));
export function disclosureSettings(value: unknown): DisclosureSetting[] | null {
  if (!Array.isArray(value) || !value.every(item => object(item) && typeof item.id === "string" && typeof item.calendarId === "string" &&
    visibility(item.visibility) && Number.isSafeInteger(item.revision) && Number(item.revision) > 0 &&
    (item.recipientIds === undefined || (Array.isArray(item.recipientIds) && item.recipientIds.length <= 50 && item.recipientIds.every(id => typeof id === "string") && new Set(item.recipientIds).size === item.recipientIds.length)))) return null;
  return value;
}
export function sharedSources(value: unknown): SharedSource[] | null {
  if (!Array.isArray(value) || !value.every(item => object(item) && typeof item.id === "string" && typeof item.userId === "string" &&
    typeof item.username === "string" && ["AVAILABILITY", "DETAILS"].includes(String(item.visibility)))) return null;
  return value;
}
export function disclosedEvents(value: unknown, sourceId: string, busy: string): CalendarEvent[] | null {
  if (!object(value) || !object(value.source) || value.source.id !== sourceId || !Array.isArray(value.items)) return null;
  const source = sharedSources([value.source])?.[0];
  if (!source) return null;
  const events: CalendarEvent[] = [];
  for (const item of value.items) {
    if (!object(item) || typeof item.id !== "string") return null;
    const event: CalendarEvent = { id: `shared:${sourceId}:${item.id}`, source: "shared", sharedBy: source.userId,
      disclosure: source.visibility, title: source.visibility === "AVAILABILITY" ? busy : typeof item.title === "string" ? item.title : busy,
      description: source.visibility === "DETAILS" && typeof item.description === "string" ? item.description : null,
      startsAt: typeof item.startsAt === "string" ? item.startsAt : "", endsAt: typeof item.endsAt === "string" ? item.endsAt : "",
      allDay: typeof item.startsAt === "string" && /^\d{4}-\d{2}-\d{2}$/.test(item.startsAt), canEdit: false, canDelete: false };
    if (!isCalendarEvent(event)) return null;
    events.push(event);
  }
  return events;
}

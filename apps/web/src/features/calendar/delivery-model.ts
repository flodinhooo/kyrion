import { editorInstant, type CalendarEditor, type CalendarEvent } from "./calendar-model";
export type DestinationSetting = { id: string | null; calendarId: string | null; enabled: boolean; revision: number };
export type DeliveryState = "RUNNING" | "SYNCED" | "OUTDATED" | "ERROR" | "CONFLICT" | "BLOCKED" | "NEEDS_REVIEW";
export type DeliveryView = { revision: number; targets: { userId: string; username: string; targetId: string | null }[];
  items: { id: string; userId: string; username: string | null; state: DeliveryState; deliveredRevision: number | null; errorCode: string | null }[] };
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const stringOrNull = (value: unknown) => value === null || typeof value === "string";
const revision = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0;
export function destinationSetting(value: unknown): DestinationSetting | null {
  if (!object(value) || !stringOrNull(value.id) || !stringOrNull(value.calendarId) || typeof value.enabled !== "boolean" || !revision(value.revision)) return null;
  return { id: typeof value.id === "string" ? value.id : null, calendarId: typeof value.calendarId === "string" ? value.calendarId : null,
    enabled: value.enabled, revision: Number(value.revision) };
}
export function deliveryView(value: unknown): DeliveryView | null {
  if (!object(value) || !revision(value.revision) || !Array.isArray(value.targets) || !Array.isArray(value.items)) return null;
  if (!value.targets.every(item => object(item) && typeof item.userId === "string" && typeof item.username === "string" && stringOrNull(item.targetId))) return null;
  if (!value.items.every(item => object(item) && typeof item.id === "string" && typeof item.userId === "string" && stringOrNull(item.username) &&
    ["RUNNING", "SYNCED", "OUTDATED", "ERROR", "CONFLICT", "BLOCKED", "NEEDS_REVIEW"].includes(String(item.state)) &&
    (item.deliveredRevision === null || revision(item.deliveredRevision)) && stringOrNull(item.errorCode))) return null;
  // Rebuild the public view: unrecognized upstream metadata is never copied.
  return { revision: Number(value.revision), targets: value.targets.map(item => ({ userId: item.userId, username: item.username, targetId: item.targetId })),
    items: value.items.map(item => ({ id: item.id, userId: item.userId, username: item.username, state: item.state,
      deliveredRevision: item.deliveredRevision, errorCode: item.errorCode })) };
}
export function householdEditorIsDirty(editor: CalendarEditor, event: CalendarEvent): boolean {
  try { return editor.title !== event.title || editor.description !== (event.description ?? "") ||
    Date.parse(editorInstant(editor, "startsAt")) !== Date.parse(event.startsAt) || Date.parse(editorInstant(editor, "endsAt")) !== Date.parse(event.endsAt);
  } catch { return true; }
}

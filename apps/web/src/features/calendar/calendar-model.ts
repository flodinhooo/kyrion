export type CalendarSource = "local" | "google" | "household" | "shared";

export type CalendarEvent = {
  id: string;
  title: string;
  description?: string | null;
  startsAt: string;
  endsAt: string;
  timeZone?: string;
  syncToGoogle?: boolean;
  source: CalendarSource;
  googleCalendarId?: string | null;
  googleEventId?: string | null;
  syncStatus?: string;
  syncError?: string | null;
  pendingDeletion?: boolean;
  allDay?: boolean;
  etag?: string;
  recurring?: boolean;
  revision?: number;
  participantIds?: string[];
  createdBy?: string;
  canEdit?: boolean;
  canDelete?: boolean;
  sharedBy?: string;
  disclosure?: "AVAILABILITY" | "DETAILS";
};

export type CalendarEditor = {
  id?: string;
  title: string;
  description: string;
  startsAt: string;
  endsAt: string;
  syncToGoogle: boolean;
  googleCalendarId?: string;
  source?: CalendarSource;
  revision?: number;
  etag?: string;
  participantIds?: string[];
};

export function localDateTimeValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function editorForCalendarDate(date: Date, now = new Date()): CalendarEditor {
  const start = new Date(date);
  const hour = Math.max(now.getHours() + 1, 9);
  start.setHours(hour, 0, 0, 0);
  const end = new Date(start);
  end.setHours(end.getHours() + 1);
  return { title: "", description: "", startsAt: localDateTimeValue(start), endsAt: localDateTimeValue(end), syncToGoogle: false };
}

export function normalizeLocalEvents(value: unknown): CalendarEvent[] {
  const items = Array.isArray(value) ? value : value && typeof value === "object" && Array.isArray((value as { items?: unknown }).items) ? (value as { items: unknown[] }).items : [];
  return items.filter((item): item is Record<string, unknown> => !!item && typeof item === "object").map((item) => ({ ...item, id: String(item.id), title: String(item.title), startsAt: String(item.startsAt), endsAt: String(item.endsAt), source: "local" as const }));
}

export function normalizeGoogleEvents(value: unknown): CalendarEvent[] {
  const items = value && typeof value === "object" && Array.isArray((value as { items?: unknown }).items) ? (value as { items: unknown[] }).items : [];
  return items.filter((item): item is Record<string, unknown> => !!item && typeof item === "object").flatMap((item) => {
    const id = typeof item.id === "string" ? item.id : null;
    const startsAt = typeof item.start === "string" ? item.start : null;
    const endsAt = typeof item.end === "string" ? item.end : null;
    if (!id || !startsAt || !endsAt) return [];
    return [{ id: `google:${id}`, title: typeof item.summary === "string" ? item.summary : "(untitled)", startsAt, endsAt, etag: typeof item.etag === "string" ? item.etag : undefined, recurring: item.recurring === true, description: typeof item.description === "string" ? item.description : null, allDay: /^\d{4}-\d{2}-\d{2}$/.test(startsAt), source: "google" as const }];
  });
}

export function editorForEvent(event: CalendarEvent): CalendarEditor {
  return { id: event.id, title: event.title, description: event.description ?? "",
    startsAt: localDateTimeValue(new Date(event.startsAt)), endsAt: localDateTimeValue(new Date(event.endsAt)),
    syncToGoogle: event.syncToGoogle ?? false, googleCalendarId: event.googleCalendarId ?? "", source: event.source, revision: event.revision, etag: event.etag,
    participantIds: event.participantIds };
}

export function isCalendarEvent(value: unknown): value is CalendarEvent {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<CalendarEvent>;
  return typeof item.id === "string" && typeof item.title === "string" &&
    typeof item.startsAt === "string" && Number.isFinite(Date.parse(item.startsAt)) &&
    typeof item.endsAt === "string" && Number.isFinite(Date.parse(item.endsAt)) &&
    (item.source === "local" || item.source === "google" || (item.source === "shared" && typeof item.sharedBy === "string" &&
      (item.disclosure === "AVAILABILITY" || item.disclosure === "DETAILS")) || (item.source === "household" &&
      Array.isArray(item.participantIds) && item.participantIds.every(id => typeof id === "string") &&
      typeof item.createdBy === "string" && typeof item.canEdit === "boolean" && typeof item.canDelete === "boolean" &&
      Number.isSafeInteger(item.revision) && (item.revision ?? -1) >= 0));
}

export type HouseholdMember = { id: string; username: string };

export function householdMembers(value: unknown): HouseholdMember[] | null {
  if (!Array.isArray(value) || !value.every(item => !!item && typeof item === "object" &&
      typeof item.id === "string" && typeof item.username === "string")) return null;
  return value;
}

export function normalizeHouseholdEvents(value: unknown): CalendarEvent[] | null {
  if (!Array.isArray(value)) return null;
  const events: CalendarEvent[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") return null;
    const event: unknown = { ...item, id: `household:${item.id}`, source: "household" };
    if (typeof item.id !== "string" || !isCalendarEvent(event)) return null;
    events.push(event);
  }
  return events;
}

export function canEditCalendarEvent(event: CalendarEvent, hasUpdate: boolean): boolean {
  if (event.source === "shared") return false;
  if (!hasUpdate) return false;
  if (event.source === "household") return event.canEdit === true;
  return event.source === "local" || (!event.allDay && !event.recurring && !!event.etag);
}

export function canDeleteCalendarEvent(event: CalendarEvent, hasDelete: boolean): boolean {
  return hasDelete && event.source !== "shared" && (event.source !== "household" || event.canDelete === true);
}

export function householdEventPayload(editor: CalendarEditor, timeZone: string) {
  const fields = { title: editor.title, description: editor.description || null,
    startsAt: new Date(editor.startsAt).toISOString(), endsAt: new Date(editor.endsAt).toISOString(), timeZone };
  return editor.id ? { ...fields, revision: editor.revision } : { ...fields, participantIds: editor.participantIds ?? [] };
}

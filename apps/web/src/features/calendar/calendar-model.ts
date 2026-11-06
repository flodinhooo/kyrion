export type CalendarSource = "local" | "google";

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
    syncToGoogle: event.syncToGoogle ?? false, googleCalendarId: event.googleCalendarId ?? "", source: event.source, revision: event.revision, etag: event.etag };
}

export function isCalendarEvent(value: unknown): value is CalendarEvent {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<CalendarEvent>;
  return typeof item.id === "string" && typeof item.title === "string" &&
    typeof item.startsAt === "string" && Number.isFinite(Date.parse(item.startsAt)) &&
    typeof item.endsAt === "string" && Number.isFinite(Date.parse(item.endsAt)) &&
    (item.source === "local" || item.source === "google");
}

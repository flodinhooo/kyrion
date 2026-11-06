import type { CalendarEvent } from "./calendar-model";
type CopyLink = { eventId: string; remoteId: string; etag: string; revision: number };
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
function instantKey(value: string): string | null {
  const parts = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!parts) return null;
  const milliseconds = Date.parse(`${parts[1]}${parts[3]}`);
  if (!Number.isFinite(milliseconds)) return null;
  const day = value.slice(0, 10);
  if (new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10) !== day) return null;
  // Keep sub-millisecond precision instead of truncating an external time change.
  return `${milliseconds}:${(parts[2] ?? "").padEnd(9, "0")}`;
}
export function ownedCopyLinks(value: unknown): CopyLink[] | null {
  if (!Array.isArray(value) || value.length > 1000) return null;
  const links: CopyLink[] = [];
  for (const item of value) {
    if (!object(item) || typeof item.eventId !== "string" || !/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(item.eventId) || typeof item.remoteId !== "string" ||
      !/^[0-9a-f]{64}$/.test(item.remoteId) || typeof item.etag !== "string" || !item.etag || item.etag.length > 512 ||
      /[\r\n]/.test(item.etag) || !Number.isSafeInteger(item.revision) || Number(item.revision) < 0) return null;
    links.push({ eventId: item.eventId, remoteId: item.remoteId, etag: item.etag, revision: Number(item.revision) });
  }
  return links;
}

// Return only own provider IDs already present in this authenticated response.
// Never infer ownership from a matching title/time or provider marker alone.
export function confirmedOwnedCopies(google: unknown, household: CalendarEvent[] | null, links: CopyLink[] | null): Set<string> {
  const hidden = new Set<string>();
  if (!household || !links || !object(google) || !Array.isArray(google.items)) return hidden;
  const native = new Map(household.filter(item => item.source === "household").map(item => [item.id, item]));
  const remote = new Map(google.items.filter(object).filter(item => typeof item.id === "string").map(item => [item.id, item]));
  for (const link of links) {
    const event = native.get(`household:${link.eventId}`);
    const copy = remote.get(link.remoteId);
    if (!event || !copy || event.revision !== link.revision || copy.etag !== link.etag || copy.kyrionId !== link.remoteId ||
      !["confirmed", "tentative"].includes(String(copy.status)) || copy.recurring !== false || typeof copy.start !== "string" || typeof copy.end !== "string" ||
      copy.start.length === 10 || copy.end.length === 10 || copy.summary !== event.title ||
      (copy.description ?? "") !== (event.description ?? "")) continue;
    const start = instantKey(copy.start); const end = instantKey(copy.end);
    if (start === null || end === null || start !== instantKey(event.startsAt) || end !== instantKey(event.endsAt)) continue;
    hidden.add(`google:${link.remoteId}`);
  }
  return hidden;
}

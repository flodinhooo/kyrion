import type {CalendarEvent} from "./calendar-model";

export type CalendarView = "shared" | "personal";

// Legacy local events belong to the household, not the signed-in account.
export function eventsForCalendarView(events: CalendarEvent[], view: CalendarView, person = "", userId = ""): CalendarEvent[] {
  return events.filter(event => {
    if (view === "personal") return event.source === "google";
    if (!person) return true;
    if (event.source === "shared") return event.sharedBy === person;
    if (event.source === "household") return event.participantIds?.includes(person) === true;
    if (event.source === "google") return person === userId;
    return false;
  });
}

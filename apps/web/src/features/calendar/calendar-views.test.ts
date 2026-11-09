import {describe, expect, it} from "vitest";
import {eventsForCalendarView} from "./calendar-views";
import type {CalendarEvent} from "./calendar-model";

const base = {title: "Appointment", startsAt: "2026-11-10T09:00:00Z", endsAt: "2026-11-10T10:00:00Z"};
const events: CalendarEvent[] = [
  {...base, id: "own-google", source: "google"},
  {...base, id: "legacy", source: "local"},
  {...base, id: "joint", source: "household", participantIds: ["me", "partner"]},
  {...base, id: "partner", source: "shared", sharedBy: "partner", disclosure: "AVAILABILITY", title: "Busy"},
];

describe("personal and shared calendar views", () => {
  it("never presents household or another person's events as private personal events", () => {
    expect(eventsForCalendarView(events, "personal").map(event => event.id)).toEqual(["own-google"]);
  });
  it("combines authorized sources without deduplicating redacted personal calendars", () => {
    expect(eventsForCalendarView(events, "shared")).toEqual(events);
  });
  it("filters a partner without leaking the viewer's Google or legacy household events into that filter", () => {
    expect(eventsForCalendarView(events, "shared", "partner", "me").map(event => event.id)).toEqual(["joint", "partner"]);
    expect(eventsForCalendarView(events, "shared", "me", "me").map(event => event.id)).toEqual(["own-google", "joint"]);
    expect(eventsForCalendarView(events, "shared", "unknown", "me")).toEqual([]);
  });
  it("does not let a shared-view filter hide personal events after switching tabs", () => {
    expect(eventsForCalendarView(events, "personal", "partner", "me")).toHaveLength(1);
  });
});

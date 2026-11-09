import {describe, expect, it} from "vitest";
import {calendarColor, calendarColors} from "./calendar-colors";
import type {CalendarEvent} from "./calendar-model";

const event: CalendarEvent = {
  id: "event",
  source: "shared",
  sharedBy: "partner",
  disclosure: "AVAILABILITY",
  title: "Busy",
  startsAt: "2026-11-10T10:00:00Z",
  endsAt: "2026-11-10T11:00:00Z"
};

describe("calendar colors", () => {
  it("keeps personal, shared household and legacy local calendars distinct", () => {
    const sources: CalendarEvent["source"][] = ["google", "household", "local"];
    expect(new Set(sources.map(source => calendarColor({...event, source}))).size).toBe(3);
    expect(calendarColor({...event, source: "google"})).toBe("personal");
  });
  it("assigns a stable member color independent of private content, dates or event identity", () => {
    const color = calendarColor(event);
    expect(calendarColor({...event, id: "another", title: "Different", startsAt: "2027-01-01T10:00:00Z"})).toBe(color);
    expect(calendarColors[color]).toMatch(/^#[0-9a-f]{6}$/);
    expect(color).not.toBe("personal");
    expect(color).not.toBe("household");
  });
});

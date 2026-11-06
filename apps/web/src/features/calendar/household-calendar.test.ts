import { describe, expect, it } from "vitest";
import { canDeleteCalendarEvent, canEditCalendarEvent, editorForEvent, householdEventPayload,
  householdMembers, normalizeHouseholdEvents } from "./calendar-model";
import { calendarMessages } from "./messages";

const fixture = { id: "one", title: "Dinner", startsAt: "2026-11-10T10:00:00Z", endsAt: "2026-11-10T11:00:00Z",
  createdBy: "creator", participantIds: ["creator", "partner"], canEdit: true, canDelete: false, revision: 4 };

describe("joint household calendar", () => {
  it("requires explicit server permissions and a revision rather than trusting mere participation", () => {
    const event = normalizeHouseholdEvents([fixture])![0];
    expect(event.id).toBe("household:one");
    expect(canEditCalendarEvent(event, true)).toBe(true);
    expect(canEditCalendarEvent(event, false)).toBe(false);
    expect(canEditCalendarEvent({ ...event, canEdit: false }, true)).toBe(false);
    expect(canDeleteCalendarEvent(event, true)).toBe(false);
    expect(canDeleteCalendarEvent({ ...event, canDelete: true }, false)).toBe(false);
    expect(normalizeHouseholdEvents([{ ...fixture, canEdit: "true" }])).toBeNull();
    expect(normalizeHouseholdEvents([{ ...fixture, revision: 0.5 }])).toBeNull();
    expect(normalizeHouseholdEvents([{ ...fixture, participantIds: [null] }])).toBeNull();
  });

  it("round trips joint edits without submitting immutable membership or provider settings", () => {
    const editor = editorForEvent(normalizeHouseholdEvents([fixture])![0]);
    expect(editor.participantIds).toEqual(["creator", "partner"]);
    const payload = householdEventPayload(editor, "Europe/Zurich");
    expect(payload).toMatchObject({ revision: 4 });
    expect(Date.parse(payload.startsAt)).toBe(Date.parse(fixture.startsAt));
    expect(Date.parse(payload.endsAt)).toBe(Date.parse(fixture.endsAt));
    expect(payload).not.toHaveProperty("participantIds");
    expect(payload).not.toHaveProperty("syncToGoogle");
    expect(payload).not.toHaveProperty("createdBy");
  });

  it("creation sends an explicit participant selection without editor identity or remote credentials", () => {
    const editor = editorForEvent(normalizeHouseholdEvents([fixture])![0]);
    const payload = householdEventPayload({ ...editor, id: undefined }, "Europe/Zurich");
    expect(payload).toHaveProperty("participantIds", ["creator", "partner"]);
    expect(payload).not.toHaveProperty("revision");
    expect(payload).not.toHaveProperty("actorId");
    expect(householdMembers([{ id: "creator", username: "Alex" }])).toEqual([{ id: "creator", username: "Alex" }]);
    expect(householdMembers([{ id: "creator", email: "private@example.test" }])).toBeNull();
  });

  it("provides matching German and English resources for shared event actions", () => {
    expect(Object.keys(calendarMessages.de).sort()).toEqual(Object.keys(calendarMessages.en).sort());
    expect(calendarMessages.de.jointInfo).not.toBe(calendarMessages.en.jointInfo);
  });
});

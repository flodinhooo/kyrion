import { describe, expect, it } from "vitest";
import { editorForCalendarDate, normalizeGoogleEvents, normalizeLocalEvents } from "./calendar-model";

describe("calendar model", () => {
  it.each([
    ["today", new Date(2026, 8, 14), "2026-09-14"],
    ["future date", new Date(2026, 8, 17), "2026-09-17"],
    ["month change", new Date(2026, 9, 1), "2026-10-01"],
  ])("uses the clicked %s as the editor date", (_, clicked, expectedDate) => {
    expect(editorForCalendarDate(clicked, new Date(2026, 8, 14, 8, 30)).startsAt).toMatch(new RegExp(`^${expectedDate}T`));
  });

  it("keeps the local calendar date across timezone offsets", () => {
    const clicked = new Date(2026, 8, 17, 0, 0);
    expect(editorForCalendarDate(clicked, new Date(2026, 8, 14, 12)).startsAt.slice(0, 10)).toBe("2026-09-17");
  });

  it("normalizes local and Google events without ID collisions", () => {
    const local = normalizeLocalEvents([{ id: "same", title: "Local", startsAt: "2026-09-17T09:00:00Z", endsAt: "2026-09-17T10:00:00Z" }]);
    const google = normalizeGoogleEvents({ items: [{ id: "same", summary: "Google", start: "2026-09-17T11:00:00Z", end: "2026-09-17T12:00:00Z" }] });
    expect(new Set([...local, ...google].map((event) => event.id)).size).toBe(2);
    expect(google[0].source).toBe("google");
  });
});

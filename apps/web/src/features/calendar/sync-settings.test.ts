import { expect, it } from "vitest";
import { isCalendarSchedule } from "./sync-settings";

it("requires explicit settings and rejects malformed intervals or timestamps", () => {
  const settings = { enabled: false, intervalSeconds: 300, running: false, lastAttemptAt: null, lastSuccessAt: null, nextAttemptAt: null, lastError: null };
  expect(isCalendarSchedule(settings)).toBe(true);
  expect(isCalendarSchedule({ ...settings, enabled: "true" })).toBe(false);
  expect(isCalendarSchedule({ ...settings, intervalSeconds: 0 })).toBe(false);
  expect(isCalendarSchedule({ ...settings, nextAttemptAt: "invalid" })).toBe(false);
});

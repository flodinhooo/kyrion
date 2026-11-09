import type {CalendarEvent} from "./calendar-model";

export const calendarColors = {
  personal: "#1d4ed8",
  household: "#0f766e",
  local: "#92400e",
  shared0: "#7e22ce",
  shared1: "#be185d",
  shared2: "#b45309",
  shared3: "#0369a1",
  shared4: "#4338ca",
  shared5: "#475569",
} as const;

export type CalendarColor = keyof typeof calendarColors;

export function calendarColor(event: CalendarEvent): CalendarColor {
  if (event.source === "google") return "personal";
  if (event.source === "household") return "household";
  if (event.source === "local") return "local";
  // Stable across dates, filters and reloads; never hash redacted event content.
  let hash = 0;
  for (const character of event.sharedBy ?? "") hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  const sharedColors = ["shared0", "shared1", "shared2", "shared3", "shared4", "shared5"] as const;
  return sharedColors[hash % sharedColors.length];
}

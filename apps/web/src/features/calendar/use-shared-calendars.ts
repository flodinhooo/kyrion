"use client";

import {useEffect, useState} from "react";
import {browserRequest} from "@/lib/browser-request";
import {disclosedEvents, sharedSources} from "./disclosure-model";
import type {CalendarEvent} from "./calendar-model";

export function useSharedCalendars(range: { start: string; end: string } | null, busyTitle: string) {
  const [snapshot, setSnapshot] = useState<{ events: CalendarEvent[]; available: boolean; error: boolean }>({
    events: [],
    available: false,
    error: false
  });
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function refresh() {
      // Clear previously authorized data before rechecking grants, also on failure.
      setSnapshot(previous => ({...previous, events: [], error: false}));
      if (document.visibilityState !== "visible") return;
      try {
        const response = await browserRequest("/api/calendar/personal-disclosure/sources", {
          cache: "no-store",
          signal: controller.signal
        });
        const sources = response.ok ? sharedSources(await response.json()) : null;
        if (!sources) throw new Error("SHARED_CALENDARS_UNAVAILABLE");
        const results = range ? await Promise.all(sources.map(async source => {
          try {
            const response = await browserRequest(`/api/calendar/personal-disclosure/sources/${encodeURIComponent(source.id)}/events?${new URLSearchParams(range)}`, {
              cache: "no-store",
              signal: controller.signal
            });
            return response.ok ? disclosedEvents(await response.json(), source.id, busyTitle) : null;
          } catch {
            return null;
          }
        })) : [];
        if (!controller.signal.aborted && document.visibilityState === "visible") {
          setSnapshot({
            events: results.flatMap(items => items ?? []),
            available: sources.length > 0,
            error: results.some(items => items === null)
          });
        }
      } catch {
        if (!controller.signal.aborted) setSnapshot(previous => ({...previous, events: [], error: true}));
      }
    }

    const timer = window.setTimeout(() => void refresh(), 0);
    const tick = () => {
      setSnapshot(previous => ({...previous, events: [], error: false}));
      setGeneration(value => value + 1);
    };
    const interval = window.setInterval(tick, 30_000);
    window.addEventListener("focus", tick);
    document.addEventListener("visibilitychange", tick);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
      window.clearInterval(interval);
      window.removeEventListener("focus", tick);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [range, busyTitle, generation]);
  return {...snapshot, refresh: () => setGeneration(value => value + 1)};
}

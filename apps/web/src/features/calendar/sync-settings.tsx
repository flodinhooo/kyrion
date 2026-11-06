"use client";

import { useEffect, useState } from "react";
import { browserRequest } from "@/lib/browser-request";
import { csrfHeader } from "@/features/auth/csrf";
import { useWorkspace } from "@/components/app-shell";
import { calendarMessages } from "./messages";

export type CalendarSchedule = { enabled: boolean; intervalSeconds: number; running: boolean;
  lastAttemptAt: string | null; lastSuccessAt: string | null; nextAttemptAt: string | null; lastError: string | null };
export function isCalendarSchedule(value: unknown): value is CalendarSchedule {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<CalendarSchedule>;
  return typeof item.enabled === "boolean" && typeof item.running === "boolean" && typeof item.intervalSeconds === "number" &&
    Number.isInteger(item.intervalSeconds) && item.intervalSeconds >= 60 && item.intervalSeconds <= 86400 &&
    [item.lastAttemptAt, item.lastSuccessAt, item.nextAttemptAt].every(date => date === null || typeof date === "string" && Number.isFinite(Date.parse(date))) &&
    (item.lastError === null || typeof item.lastError === "string");
}

export function CalendarSyncSettings({ schedule, onChange }: { schedule: CalendarSchedule | null; onChange: (value: CalendarSchedule) => void }) {
  const { locale } = useWorkspace();
  const text = calendarMessages[locale] ?? calendarMessages.en;
  const [draftEnabled, setEnabled] = useState<boolean | null>(null);
  const [draftInterval, setIntervalSeconds] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); let inFlight = false;
    async function load() {
      if(inFlight) return; inFlight = true;
      try {
        const response = await browserRequest("/api/calendar/sync/settings", { cache: "no-store", signal: controller.signal });
        const value: unknown = await response.json();
        if(!response.ok || !isCalendarSchedule(value)) throw new Error();
        if(!controller.signal.aborted) { onChange(value); setError(false); }
      } catch { if(!controller.signal.aborted) setError(true); } finally { inFlight = false; }
    }
    void load(); const interval = window.setInterval(() => void load(), 15_000);
    return () => { controller.abort(); window.clearInterval(interval); };
  }, [onChange]);
  async function save() {
    if(!schedule || busy) return; setBusy(true);
    try {
      const response = await browserRequest("/api/calendar/sync/settings", { method: "PUT", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({ enabled: draftEnabled ?? schedule.enabled, intervalSeconds: draftInterval ?? schedule.intervalSeconds }) });
      const value: unknown = await response.json(); if(!response.ok || !isCalendarSchedule(value)) throw new Error();
      onChange(value); setEnabled(null); setIntervalSeconds(null); setError(false);
    } catch { setError(true); } finally { setBusy(false); }
  }
  const timestamp = (value: string | null) => value ? new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "medium" }).format(new Date(value)) : text.notYet;
  return <article className="connection-card">
    <label><input type="checkbox" disabled={!schedule || busy} checked={draftEnabled ?? schedule?.enabled ?? false} onChange={event => setEnabled(event.target.checked)} /> {text.autoSync}</label>
    <p>{text.autoConsent}</p>
    <label>{text.interval}<input type="number" min={60} max={86400} step={1} disabled={!schedule || busy} value={draftInterval ?? schedule?.intervalSeconds ?? 300} onChange={event => setIntervalSeconds(Number(event.target.value))} /></label>
    <button className="calendar-secondary" type="button" disabled={!schedule || busy} onClick={() => void save()}>{busy ? text.saving : text.save}</button>
    {schedule && <p role="status">{schedule.running ? text.syncing : schedule.enabled ? text.autoEnabled : text.autoDisabled} · {text.lastAttempt}: {timestamp(schedule.lastAttemptAt)} · {text.nextAttempt}: {timestamp(schedule.nextAttemptAt)}</p>}
    {schedule?.lastError && <p role="alert">{schedule.lastError === "CALENDAR_SYNC_CONFLICT" ? text.conflict : text.syncError}</p>}
    {error && <p role="alert">{text.scheduleError}</p>}
  </article>;
}

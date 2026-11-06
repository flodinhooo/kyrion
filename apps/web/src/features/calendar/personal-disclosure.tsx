"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { browserRequest } from "@/lib/browser-request";
import { csrfHeader } from "@/features/auth/csrf";
import { calendarMessages } from "./messages";
import { disclosureSettings, sharedSources, disclosedEvents, type DisclosureSetting, type SharedSource, type Visibility } from "./disclosure-model";
import type { CalendarEvent } from "./calendar-model";

type Props = {
  locale: "de" | "en"; canUpdate: boolean;
  calendars: { id: string; summary: string; accessRole: string }[];
  range: { start: string; end: string } | null;
  onEvents: (events: CalendarEvent[]) => void;
};

export function PersonalCalendarDisclosure({ locale, canUpdate, calendars, range, onEvents }: Props) {
  const text = calendarMessages[locale] ?? calendarMessages.en;
  const [settings, setSettings] = useState<DisclosureSetting[] | null>(null);
  const [draft, setDraft] = useState<Record<string, Visibility>>({});
  const [sources, setSources] = useState<SharedSource[]>([]);
  const [selected, setSelected] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [sharedError, setSharedError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generation, setGeneration] = useState(0);
  const sequence = useRef(0);

  const loadSettings = useCallback(async () => {
    try {
      const response = await browserRequest("/api/calendar/personal-disclosure", { cache: "no-store" });
      const parsed = response.ok ? disclosureSettings(await response.json()) : null;
      setSettings(parsed); setDraft({});
    } catch { setSettings(null); }
  }, []);
  useEffect(() => { const timer = window.setTimeout(() => void loadSettings(), 0); return () => window.clearTimeout(timer); }, [loadSettings]);

  useEffect(() => {
    const controller = new AbortController();
    const current = ++sequence.current;
    async function refresh() {
      // Remove the old authorized representation before any request, including failures.
      onEvents([]);
      if (document.visibilityState !== "visible") return;
      try {
        const response = await browserRequest("/api/calendar/personal-disclosure/sources", { cache: "no-store", signal: controller.signal });
        const items = response.ok ? sharedSources(await response.json()) : null;
        if (controller.signal.aborted || current !== sequence.current || document.visibilityState !== "visible") return;
        setSources(items ?? []);
        if (!items) { setSharedError(!!selected); return; }
        if (!selected) { setSharedError(false); return; }
        if (!items.some(item => item.id === selected)) { setSharedError(true); return; }
        if (!range) return;
        const query = new URLSearchParams(range);
        const events = await browserRequest(`/api/calendar/personal-disclosure/sources/${encodeURIComponent(selected)}/events?${query}`, { cache: "no-store", signal: controller.signal });
        const parsed = events.ok ? disclosedEvents(await events.json(), selected, text.sharedBusy) : null;
        if (controller.signal.aborted || current !== sequence.current || document.visibilityState !== "visible") return;
        setSharedError(parsed === null); onEvents(parsed ?? []);
      } catch { if (!controller.signal.aborted && current === sequence.current) { onEvents([]); setSharedError(!!selected); } }
    }
    const timer = window.setTimeout(() => void refresh(), 0);
    // Prevent overlapping refreshes: each tick creates a new effect/AbortController.
    const tick = () => { onEvents([]); setGeneration(value => value + 1); };
    const interval = window.setInterval(tick, 30_000);
    window.addEventListener("focus", tick);
    document.addEventListener("visibilitychange", tick);
    return () => { controller.abort(); window.clearTimeout(timer); window.clearInterval(interval); window.removeEventListener("focus", tick); document.removeEventListener("visibilitychange", tick); };
  }, [selected, range, onEvents, text.sharedBusy, generation]);

  async function save(calendarId: string) {
    const old = settings?.find(item => item.calendarId === calendarId);
    const mode = draft[calendarId] ?? old?.visibility ?? "PRIVATE";
    if (mode !== "PRIVATE" && !window.confirm(text.disclosureConfirm)) return;
    setSaving(true); setMessage(null);
    try {
      const response = await browserRequest("/api/calendar/personal-disclosure", { method: "PUT",
        headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({ calendarId, visibility: mode, revision: old?.revision ?? 0 }) });
      if (!response.ok) {
        const error: unknown = await response.json().catch(() => null);
        setMessage(error && typeof error === "object" && "code" in error && error.code === "CALENDAR_DISCLOSURE_CONFLICT" ? text.disclosureConflict : text.disclosureError);
        return;
      }
      await loadSettings(); setMessage(text.disclosureSaved);
    } catch { setMessage(text.disclosureError); } finally { setSaving(false); }
  }
  const choices = calendars.filter(item => item.id !== "primary");
  for (const setting of settings ?? []) if (!choices.some(item => item.id === setting.calendarId))
    choices.push({ id: setting.calendarId, summary: text.disclosureUnknown, accessRole: "none" });

  return <article className="connection-card calendar-panel">
    <label>{text.sharedCalendar}<select value={selected} onChange={event => { onEvents([]); setSelected(event.target.value); }}>
      <option value="">{text.sharedNone}</option>
      {sources.map(source => <option key={source.id} value={source.id}>{source.username} · {source.visibility === "AVAILABILITY" ? text.disclosureAvailability : text.disclosureDetails} · {sources.filter(item => item.userId === source.userId).findIndex(item => item.id === source.id) + 1}</option>)}
    </select></label>
    {sharedError && <p role="alert">{text.sharedError}</p>}
    <details><summary>{text.disclosureTitle}</summary><p>{text.disclosureConsent}</p><p>{text.sharedAudience}</p>
      {settings === null && <p role="status">{text.disclosureUnavailable}</p>}
      <button className="calendar-secondary" type="button" disabled={saving} onClick={() => void loadSettings()}>{text.disclosureReload}</button>
      {settings !== null && choices.map(calendar => {
        const mode = draft[calendar.id] ?? settings.find(item => item.calendarId === calendar.id)?.visibility ?? "PRIVATE";
        return <fieldset key={calendar.id}><legend>{calendar.summary}</legend>
          <select aria-label={`${text.disclosureTitle}: ${calendar.summary}`} disabled={!canUpdate || saving} value={mode}
            onChange={event => setDraft({ ...draft, [calendar.id]: event.target.value as Visibility })}>
            <option value="PRIVATE">{text.disclosurePrivate}</option>
            <option value="AVAILABILITY" disabled={["none", "freeBusyReader"].includes(calendar.accessRole)}>{text.disclosureAvailability}</option>
            <option value="DETAILS" disabled={["none", "freeBusyReader"].includes(calendar.accessRole)}>{text.disclosureDetails}</option>
          </select>
          <button className="calendar-secondary" type="button" disabled={!canUpdate || saving} onClick={() => void save(calendar.id)}>{text.disclosureSave}</button>
        </fieldset>;
      })}
      {message && <p role="status">{message}</p>}
    </details>
  </article>;
}

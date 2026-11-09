"use client";
import { useCallback, useEffect, useState } from "react";
import { browserRequest } from "@/lib/browser-request";
import { csrfHeader } from "@/features/auth/csrf";
import { calendarMessages } from "./messages";
import { destinationSetting, type DestinationSetting } from "./delivery-model";

export function HouseholdDestination({ locale, canUpdate, canEnable, calendars }: {
  locale: "de" | "en"; canUpdate: boolean; canEnable: boolean;
  calendars: { id: string; summary: string; accessRole: string }[];
}) {
  const text = calendarMessages[locale] ?? calendarMessages.en;
  const [setting, setSetting] = useState<DestinationSetting | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [calendar, setCalendar] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const response = await browserRequest("/api/calendar/household-destination", { cache: "no-store" });
      const current = response.ok ? destinationSetting(await response.json()) : null;
      setSetting(current); setEnabled(current?.enabled ?? false); setCalendar(current?.calendarId ?? "");
    } catch { setSetting(null); }
  }, []);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);
  async function save() {
    if (!setting || saving || (enabled && !window.confirm(text.destinationConfirm))) return;
    setSaving(true); setMessage(null);
    try {
      const response = await browserRequest("/api/calendar/household-destination", { method: "PUT", headers: { "Content-Type": "application/json", ...csrfHeader() },
        signal: AbortSignal.timeout(115_000),
        body: JSON.stringify({ calendarId: enabled ? calendar : null, revision: setting.revision }) });
      if (!response.ok) { setMessage(text.destinationError); return; }
      await load(); setMessage(text.destinationSaved);
    } catch { setMessage(text.destinationError); } finally { setSaving(false); }
  }
  const choices = calendars.filter(item => item.id !== "primary" && ["owner", "writer"].includes(item.accessRole));
  return <article className="connection-card calendar-panel calendar-destination">
    <div><h2>{text.destinationHeading}</h2><p>{text.destinationSummary}</p></div>
    {setting === null ? <p role="status">{text.destinationUnavailable}</p> : <>
      <label className="calendar-checkbox calendar-destination-toggle"><input type="checkbox" checked={enabled}
                                                                              disabled={!canUpdate || saving || (!canEnable && !enabled)}
                                                                              onChange={event => setEnabled(event.target.checked)}/><span>{text.destinationToggle}</span></label>
      {enabled && <label>{text.target}<small>{text.destinationChooseHint}</small><select value={calendar}
                                                                                         disabled={!canEnable || saving}
                                                                                         onChange={event => setCalendar(event.target.value)}>
        <option value="">{text.select}</option>{choices.map(item => <option key={item.id} value={item.id}>{item.summary}</option>)}
      </select></label>}
      {enabled && choices.length === 0 && <p role="status">{text.destinationNoCalendar}</p>}
      <p className="calendar-destination-note">{text.destinationManual}</p>
    </>}
    <details className="calendar-help">
      <summary>{text.destinationMore}</summary>
      <p>{text.destinationConsent}</p><p>{text.destinationRetention}</p></details>
    <div className="calendar-dialog-actions">
      {setting !== null && <button className="calendar-primary" type="button"
                                   disabled={!canUpdate || saving || (enabled && (!canEnable || !choices.some(item => item.id === calendar)))}
                                   onClick={() => void save()}>{saving ? text.saving : text.destinationSave}</button>}
      <button className="calendar-secondary" type="button" disabled={saving}
              onClick={() => void load()}>{text.disclosureReload}</button>
    </div>
    {message && <p role="status">{message}</p>}
  </article>;
}

"use client";

import {useCallback, useEffect, useState} from "react";
import { browserRequest } from "@/lib/browser-request";
import { csrfHeader } from "@/features/auth/csrf";
import { calendarMessages } from "./messages";
import {disclosureSettings, type DisclosureSetting, type Visibility} from "./disclosure-model";
import {householdMembers, type HouseholdMember} from "./calendar-model";
import {useWorkspace} from "@/components/app-shell";

type Props = {
  locale: "de" | "en"; canUpdate: boolean;
  calendars: { id: string; summary: string; accessRole: string }[];
};

export function PersonalCalendarDisclosure({locale, canUpdate, calendars}: Props) {
  const text = calendarMessages[locale] ?? calendarMessages.en;
  const {userId} = useWorkspace();
  const [settings, setSettings] = useState<DisclosureSetting[] | null>(null);
  const [draft, setDraft] = useState<Record<string, Visibility>>({});
  const [recipients, setRecipients] = useState<Record<string, string[]>>({});
  const [members, setMembers] = useState<HouseholdMember[] | null>(null);
  const [supported, setSupported] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const loadSettings = useCallback(async () => {
    try {
      const response = await browserRequest("/api/calendar/personal-disclosure", { cache: "no-store" });
      const parsed = response.ok ? disclosureSettings(await response.json()) : null;
      setSupported(response.headers.get("X-Kyrion-Calendar-Recipients") === "selected-v1");
      setSettings(parsed);
      setDraft({});
      setRecipients({});
    } catch { setSettings(null); }
  }, []);
  useEffect(() => { const timer = window.setTimeout(() => void loadSettings(), 0); return () => window.clearTimeout(timer); }, [loadSettings]);
  useEffect(() => {
    const controller = new AbortController();
    void browserRequest("/api/calendar/household-events/members", {cache: "no-store", signal: controller.signal})
      .then(async response => response.ok ? householdMembers(await response.json()) : null)
      .then(value => {
        if (!controller.signal.aborted) setMembers(value);
      }).catch(() => {
        if (!controller.signal.aborted) setMembers(null);
      });
    return () => controller.abort();
  }, []);

  async function save(calendarId: string) {
    const old = settings?.find(item => item.calendarId === calendarId);
    const mode = draft[calendarId] ?? old?.visibility ?? "PRIVATE";
    if (mode !== "PRIVATE" && (!supported || members === null)) return;
    const recipientIds = mode === "PRIVATE" ? [] : recipients[calendarId] ?? old?.recipientIds ?? [];
    if (mode !== "PRIVATE" && recipientIds.length === 0) return;
    if (mode !== "PRIVATE" && !window.confirm(text.selectedDisclosureConfirm)) return;
    setSaving(true); setMessage(null);
    try {
      const response = await browserRequest("/api/calendar/personal-disclosure", { method: "PUT",
        headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({
          calendarId,
          visibility: mode,
          revision: old?.revision ?? 0, ...(supported ? {recipientIds} : {})
        })
      });
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
    <h2>{text.disclosureTitle}</h2><p>{text.selectedDisclosureConsent}</p><p>{text.sharedAudience}</p>
    {!supported && settings !== null && <p role="status">{text.recipientsUpgrade}</p>}
      {settings === null && <p role="status">{text.disclosureUnavailable}</p>}
      <button className="calendar-secondary" type="button" disabled={saving} onClick={() => void loadSettings()}>{text.disclosureReload}</button>
      {settings !== null && choices.map(calendar => {
        const mode = draft[calendar.id] ?? settings.find(item => item.calendarId === calendar.id)?.visibility ?? "PRIVATE";
        const selected = recipients[calendar.id] ?? settings.find(item => item.calendarId === calendar.id)?.recipientIds ?? [];
        const people = members?.filter(member => member.id !== userId) ?? [];
        return <fieldset className="calendar-sharing-row" key={calendar.id}>
          <legend>{calendar.summary}</legend>
          <select aria-label={`${text.disclosureTitle}: ${calendar.summary}`} disabled={!canUpdate || saving} value={mode}
                  onChange={event => {
                    const value = event.target.value;
                    if (value === "PRIVATE" || value === "AVAILABILITY" || value === "DETAILS") setDraft({
                      ...draft,
                      [calendar.id]: value
                    });
                  }}>
            <option value="PRIVATE">{text.disclosurePrivate}</option>
            <option value="AVAILABILITY"
                    disabled={!supported || ["none", "freeBusyReader"].includes(calendar.accessRole)}>{text.disclosureAvailability}</option>
            <option value="DETAILS"
                    disabled={!supported || ["none", "freeBusyReader"].includes(calendar.accessRole)}>{text.disclosureDetails}</option>
          </select>
          {supported && mode !== "PRIVATE" && <fieldset className="calendar-recipient-list">
            <legend>{text.recipientsTitle}</legend>
            <p>{text.recipientsHint}</p>
            {members === null && <p role="status">{text.membersUnavailable}</p>}
            {members !== null && people.length === 0 && <p>{text.recipientsEmpty}</p>}
            {people.map(member => <label className="calendar-recipient" key={member.id}><input type="checkbox"
                                                                                               checked={selected.includes(member.id)}
                                                                                               disabled={!canUpdate || saving}
                                                                                               onChange={event => setRecipients({
                                                                                                 ...recipients,
                                                                                                 [calendar.id]: event.target.checked ? [...selected, member.id] : selected.filter(id => id !== member.id)
                                                                                               })}/><span>{member.username}</span></label>)}
            {selected.filter(id => !people.some(person => person.id === id)).map(id => <label
              className="calendar-recipient" key={id}><input type="checkbox" checked disabled={!canUpdate || saving}
                                                             onChange={() => setRecipients({
                                                               ...recipients,
                                                               [calendar.id]: selected.filter(value => value !== id)
                                                             })}/><span>{text.formerParticipant}</span></label>)}
          </fieldset>}
          <button className="calendar-secondary" type="button"
                  disabled={!canUpdate || saving || (mode !== "PRIVATE" && (!supported || members === null || selected.length === 0))}
                  onClick={() => void save(calendar.id)}>{text.disclosureSave}</button>
        </fieldset>;
      })}
      {message && <p role="status">{message}</p>}
  </article>;
}

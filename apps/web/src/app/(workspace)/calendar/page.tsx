"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import { useWorkspace } from "@/components/app-shell";
import { browserRequest } from "@/lib/browser-request";
import { csrfHeader } from "@/features/auth/csrf";
import { editorForCalendarDate, editorForEvent, isCalendarEvent, canEditCalendarEvent, canDeleteCalendarEvent,
  editorInstant, CalendarTimeError,
  householdMembers, householdEventPayload, type HouseholdMember, type CalendarEditor, type CalendarEvent } from "@/features/calendar/calendar-model";
import { CalendarSyncSettings, type CalendarSchedule } from "@/features/calendar/sync-settings";
import { calendarMessages } from "@/features/calendar/messages";
import { PersonalCalendarDisclosure } from "@/features/calendar/personal-disclosure";
import { HouseholdDestination } from "@/features/calendar/household-destination";
import { HouseholdDeliveriesPanel } from "@/features/calendar/household-deliveries";
import { householdEditorIsDirty } from "@/features/calendar/delivery-model";

type RemoteCalendar = { id: string; summary: string; accessRole: string; primary?: boolean };
function calendarList(value: unknown): RemoteCalendar[] {
  if (!value || typeof value !== "object" || !("items" in value) || !Array.isArray(value.items)) return [];
  return value.items.filter((item): item is RemoteCalendar => !!item && typeof item === "object" &&
    typeof item.id === "string" && typeof item.summary === "string" && typeof item.accessRole === "string");
}

export default function CalendarPage() {
  const { t, locale, permissions, userId } = useWorkspace();
  const text = calendarMessages[locale] ?? calendarMessages.en;
  const [schedule, setSchedule] = useState<CalendarSchedule | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [sharedEvents, setSharedEvents] = useState<CalendarEvent[]>([]);
  const [sharedDetailId, setSharedDetailId] = useState<string | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [googleState, setGoogleState] = useState("loading");
  const [googleCode, setGoogleCode] = useState<string | null>(null);
  const [editor, setEditor] = useState<CalendarEditor | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [calendars, setCalendars] = useState<RemoteCalendar[]>([]);
  const [calendarId, setCalendarId] = useState("primary");
  const [range, setRange] = useState<{ start: string; end: string } | null>(null);
  const [members, setMembers] = useState<HouseholdMember[]>([]);
  const [membersReady, setMembersReady] = useState(false);
  const [householdState, setHouseholdState] = useState("loading");
  const [copiesUnavailable, setCopiesUnavailable] = useState(false);
  const [personFilter, setPersonFilter] = useState("");
  const sequence = useRef(0);
  const editorFeedback = useRef<HTMLParagraphElement>(null);
  const canCreate = permissions.includes("calendar:create");
  const canUpdate = permissions.includes("calendar:update");
  const canDelete = permissions.includes("calendar:delete");
  const canSync = canCreate && canUpdate && canDelete;
  const writable = calendars.filter(item => ["owner", "writer"].includes(item.accessRole));
  const selectedEvent = events.find(item => item.id === editor?.id);
  const sharedDetail = sharedEvents.find(item => item.id === sharedDetailId);
  const statuses: Record<string, string> = { local: text.localStatus, pending: text.pending, synced: text.synced,
    read_error: text.error, error: text.error, conflict: text.conflict, configuration_required: text.configuration_required };

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!range) return;
    const current = ++sequence.current;
    const query = new URLSearchParams({ ...range, calendarId });
    const response = await browserRequest(`/api/calendar/events?${query}`, { cache: "no-store", signal });
    const value: unknown = await response.json();
    if (current !== sequence.current || signal?.aborted) return;
    if (!response.ok || !value || typeof value !== "object" || !("items" in value) ||
        !Array.isArray(value.items) || !value.items.every(isCalendarEvent)) throw new Error();
    setEvents(value.items);
    const household = "household" in value ? value.household : null;
    setHouseholdState(household && typeof household === "object" && "status" in household && household.status === "ready" ? "ready" : "error");
    const copies = "copies" in value ? value.copies : null;
    setCopiesUnavailable(!!copies && typeof copies === "object" && "status" in copies && copies.status === "unavailable");
    const google = "google" in value ? value.google : null;
    setGoogleState(google && typeof google === "object" && "status" in google && typeof google.status === "string" ? google.status : "error");
    setGoogleCode(google && typeof google === "object" && "code" in google && typeof google.code === "string" ? google.code : null);
    setState("ready");
  }, [range, calendarId]);

  useEffect(() => {
    if (message) editorFeedback.current?.scrollIntoView({ block: "center" });
  }, [message]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => { void load(controller.signal).catch(() => { if (!controller.signal.aborted) setState("error"); }); }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [load]);
  useEffect(() => {
    let disposed = false;
    void browserRequest("/api/integrations/google/calendar/calendars", { cache: "no-store" })
      .then(async response => response.ok ? calendarList(await response.json()) : [])
      .then(items => { if (!disposed) { setCalendars(items); const primary = items.find(item => item.primary); if (primary) setCalendarId(current => current === "primary" ? primary.id : current); } }).catch(() => {});
    return () => { disposed = true; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void browserRequest("/api/calendar/household-events/members", { cache: "no-store", signal: controller.signal })
      .then(async response => response.ok ? householdMembers(await response.json()) : null)
      .then(items => { if (!controller.signal.aborted) { setMembers(items ?? []); setMembersReady(items !== null); } })
      .catch(() => { if (!controller.signal.aborted) { setMembers([]); setMembersReady(false); } });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if(!schedule?.enabled) return;
    const interval = window.setInterval(() => { void load().catch(() => setState("error")); }, schedule.intervalSeconds * 1000);
    return () => window.clearInterval(interval);
  }, [load, schedule?.enabled, schedule?.intervalSeconds]);

  async function save() {
    if (!editor || saving) return;
    setSaving(true); setMessage(null);
    try {
      const remote = editor.source === "google";
      const household = editor.source === "household";
      const url = household ? `/api/calendar/household-events${editor.id ? `/${encodeURIComponent(editor.id.slice(10))}` : ""}` :
        remote ? `/api/integrations/google/calendar/events/${encodeURIComponent(editor.id!.slice(7))}` : editor.id ? `/api/calendar/events/${editor.id}` : "/api/calendar/events";
      const response = await browserRequest(url, {
        method: editor.id ? "PUT" : "POST", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify(household ? householdEventPayload(editor, Intl.DateTimeFormat().resolvedOptions().timeZone) : remote ? { calendarId, summary: editor.title, description: editor.description || null,
          start: editorInstant(editor, "startsAt"), end: editorInstant(editor, "endsAt"), etag: editor.etag } : { title: editor.title, description: editor.description || null,
          startsAt: editorInstant(editor, "startsAt"), endsAt: editorInstant(editor, "endsAt"),
          timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone, syncToGoogle: editor.syncToGoogle,
          googleCalendarId: editor.googleCalendarId || null, revision: editor.revision }),
      });
      if (!response.ok) {
        const error: unknown = await response.json().catch(() => null);
        const code = error && typeof error === "object" && "code" in error ? error.code : null;
        setMessage(code === "HOUSEHOLD_CALENDAR_CONFLICT" ? text.jointConflict : code === "HOUSEHOLD_CALENDAR_INVALID" ? text.jointInvalid : text.saveError);
        return;
      }
      setEditor(null); await load();
    } catch (error) { setMessage(error instanceof CalendarTimeError ? text.invalidLocalTime : text.saveError); } finally { setSaving(false); }
  }
  async function remove() {
    if (!editor?.id || saving || !window.confirm(editor.source === "household" ? text.jointDelete : text.confirmDelete)) return;
    setSaving(true);
    try {
      const remote = editor.source === "google";
      const query = new URLSearchParams({ calendarId, etag: editor.etag ?? "" });
      const url = editor.source === "household" ? `/api/calendar/household-events/${encodeURIComponent(editor.id.slice(10))}?revision=${editor.revision}&retainExternalCopies=true` :
        remote ? `/api/integrations/google/calendar/events/${encodeURIComponent(editor.id.slice(7))}?${query}` : `/api/calendar/events/${editor.id}${editor.revision == null ? "" : `?revision=${editor.revision}`}`;
      const response = await browserRequest(url, { method: "DELETE", headers: csrfHeader() });
      if (!response.ok) throw new Error();
      setEditor(null); await load();
    } catch { setMessage(text.deleteError); } finally { setSaving(false); }
  }
  async function sync() {
    setSaving(true); setMessage(null);
    try {
      const response = await browserRequest("/api/calendar/sync", { method: "POST", headers: csrfHeader() });
      if (!response.ok) throw new Error();
      setMessage(text.syncDone); await load();
    } catch { setMessage(text.syncError); } finally { setSaving(false); }
  }
  const combinedEvents = [...events, ...sharedEvents];
  const filtered = combinedEvents.filter(event => !personFilter || (event.source === "shared" ? event.sharedBy === personFilter : event.source !== "household" || event.participantIds?.includes(personFilter)));
  const visible = filtered.filter(event => !range || (event.allDay ? event.endsAt > range.start.slice(0, 10) && event.startsAt < range.end.slice(0, 10) : Date.parse(event.endsAt) > Date.parse(range.start) && Date.parse(event.startsAt) < Date.parse(range.end)));
  const calendarEvents = filtered.map(event => ({ id: event.id,
    title: `${event.source === "shared" ? `${text.sharedSource} · ` : event.source === "household" ? `${text.jointSource} · ` : event.source === "google" ? "Google · " : ""}${event.title}${event.pendingDeletion ? ` · ${text.deletion}` : event.syncStatus && !["local", "synced"].includes(event.syncStatus) ? ` · ${statuses[event.syncStatus] ?? text.error}` : ""}`,
    start: event.startsAt, end: event.endsAt, allDay: event.allDay,
    classNames: event.source === "google" ? ["calendar-event-google"] : ["calendar-event-local"],
  }));
  return <section className="plugins-stage integration-detail calendar-page">
    <header className="plugins-header"><div><h1>{t.calendarTitle}</h1><p>{text.subtitle}</p></div>
      <div className="calendar-actions">
        {canCreate && <button className="calendar-primary" type="button" onClick={() => { setMessage(null); setEditor(editorForCalendarDate(new Date())); }}>+ {text.create}</button>}
        {canCreate && householdState === "ready" && membersReady && <button className="calendar-primary" type="button" onClick={() => { setMessage(null); setEditor({ ...editorForCalendarDate(new Date()), source: "household", participantIds: [userId] }); }}>+ {text.jointCreate}</button>}
        <button className="calendar-secondary" type="button" disabled={saving} onClick={() => void load().catch(() => setState("error"))}>{text.refresh}</button>
        {canSync && <button className="calendar-secondary" type="button" disabled={saving} onClick={() => void sync()}>{saving ? text.syncing : text.sync}</button>}
        <Link className="calendar-secondary" href="/plugins/google">{text.googleSettings}</Link>
      </div>
    </header>
    {canSync && <CalendarSyncSettings schedule={schedule} onChange={setSchedule} />}
    <PersonalCalendarDisclosure locale={locale} canUpdate={canUpdate} calendars={calendars} range={range} onEvents={setSharedEvents} />
    <HouseholdDestination locale={locale} canUpdate={canUpdate} canEnable={canCreate && canUpdate} calendars={calendars} />
    {membersReady && householdState === "ready" && <label>{text.participantFilter}<select value={personFilter} onChange={event => setPersonFilter(event.target.value)}>
      <option value="">{text.allPeople}</option>{members.map(member => <option key={member.id} value={member.id}>{member.username}</option>)}
    </select></label>}
    {calendars.length > 0 && <label>{text.viewCalendar}<select value={calendarId} onChange={event => { setState("loading"); setCalendarId(event.target.value); }}>
      <option value="primary">Google · {text.select}</option>{calendars.map(item => <option key={item.id} value={item.id}>{item.summary}</option>)}
    </select></label>}
    <article className="connection-card calendar-panel">
      <FullCalendar plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]} locale={locale} initialView="dayGridMonth" firstDay={1}
        height="auto" expandRows headerToolbar={{ left: "prev,next today", center: "title", right: "dayGridMonth,timeGridWeek,timeGridDay" }}
        buttonText={{ today: text.today, month: text.month, week: text.week, day: text.day }}
        datesSet={info => { setRange(current => current?.start === info.startStr && current?.end === info.endStr ? current : { start: info.startStr, end: info.endStr }); }}
        dateClick={info => { if (canCreate) { setMessage(null); setEditor(editorForCalendarDate(info.date)); } }} events={calendarEvents}
        eventClick={info => { const found = combinedEvents.find(event => event.id === info.event.id); if (found?.source === "shared") setSharedDetailId(found.id); else if (found && canEditCalendarEvent(found, canUpdate)) { setMessage(null); setEditor(editorForEvent(found)); } else setMessage(found?.source === "household" ? text.jointReadOnly : found?.source === "google" ? text.readOnly : text.localStatus); }} />
      {state === "loading" && <p role="status">{text.loading}</p>}
      {state === "error" && <p role="alert">{text.loadError}</p>}
      {state === "ready" && visible.length === 0 && <p>{text.empty}</p>}
      {googleState === "error" && <p role="alert">{googleCode === "GOOGLE_REAUTHORIZATION_REQUIRED" ? text.reauthorize : text.googleError}</p>}
      {googleState === "disconnected" && <p role="status">{text.disconnected}</p>}
      {householdState === "error" && <p role="status">{text.jointUnavailable}</p>}
      {householdState === "ready" && !membersReady && <p role="status">{text.membersUnavailable}</p>}
      {copiesUnavailable && <p role="status">{text.copiesUnavailable}</p>}
      {message && <p role="status">{message}</p>}
    </article>
    {sharedDetail && <div className="calendar-dialog-backdrop"><article className="calendar-dialog" role="dialog" aria-modal="true" aria-labelledby="shared-calendar-detail-title">
      <h2 id="shared-calendar-detail-title">{sharedDetail.title}</h2><p>{text.sharedReadOnly}</p>
      {sharedDetail.description && <p style={{ whiteSpace: "pre-wrap" }}>{sharedDetail.description}</p>}
      <p>{text.start}: {sharedDetail.allDay ? sharedDetail.startsAt : new Date(sharedDetail.startsAt).toLocaleString(locale)}</p>
      <p>{text.end}: {sharedDetail.allDay ? sharedDetail.endsAt : new Date(sharedDetail.endsAt).toLocaleString(locale)}</p>
      <button className="calendar-secondary" type="button" onClick={() => setSharedDetailId(null)}>{text.cancel}</button>
    </article></div>}
    {editor && <div className="calendar-dialog-backdrop"><form className="calendar-dialog" onSubmit={event => { event.preventDefault(); void save(); }}>
      <h2>{editor.id ? text.edit : text.create}</h2>
      {selectedEvent && <p>{text.source}: {selectedEvent.source === "household" ? text.jointSource : selectedEvent.source === "google" ? "Google" : text.local} · {selectedEvent.source === "google" ? calendars.find(item => item.id === calendarId)?.summary : selectedEvent.pendingDeletion ? text.deletion : statuses[selectedEvent.syncStatus ?? "local"]}</p>}
      {editor.source === "household" && <fieldset><legend>{text.participants}</legend><p>{text.jointInfo}</p>
        {editor.id ? <p>{(editor.participantIds ?? []).map(id => members.find(member => member.id === id)?.username ?? text.formerParticipant).join(", ")}<br />{text.participantsFixed}</p> : <>
          <button className="calendar-secondary" type="button" onClick={() => setEditor({ ...editor, participantIds: members.map(member => member.id) })}>{text.selectEveryone}</button>
          {members.map(member => <label className="calendar-checkbox" key={member.id}><input type="checkbox" checked={editor.participantIds?.includes(member.id) ?? false} disabled={member.id === userId}
            onChange={event => setEditor({ ...editor, participantIds: event.target.checked ? [...(editor.participantIds ?? []), member.id] : editor.participantIds?.filter(id => id !== member.id) })} />{member.username}</label>)}
        </>}
      </fieldset>}
      <label>{text.title}<input required maxLength={500} value={editor.title} onChange={event => setEditor({ ...editor, title: event.target.value })} /></label>
      <label>{text.description}<textarea maxLength={10000} value={editor.description} onChange={event => setEditor({ ...editor, description: event.target.value })} /></label>
      <label>{text.start}<input required type="datetime-local" value={editor.startsAt} onChange={event => setEditor({ ...editor, startsAt: event.target.value })} /></label>
      <label>{text.end}<input required type="datetime-local" value={editor.endsAt} onChange={event => setEditor({ ...editor, endsAt: event.target.value })} /></label>
      {editor.source === "household" && editor.id && selectedEvent && <HouseholdDeliveriesPanel key={`${editor.id}:${editor.revision}`}
        eventId={editor.id.slice(10)} revision={editor.revision ?? 0} dirty={householdEditorIsDirty(editor, selectedEvent)}
        disabled={saving} locale={locale} onBusyChange={setSaving} />}
      {editor.source !== "google" && editor.source !== "household" && <label className="calendar-checkbox"><input type="checkbox" checked={editor.syncToGoogle} disabled={!canSync} onChange={event => setEditor({ ...editor, syncToGoogle: event.target.checked })} />{text.export}</label>}
      {editor.source !== "google" && editor.source !== "household" && editor.syncToGoogle && <label>{text.target}<select required value={editor.googleCalendarId ?? ""} onChange={event => setEditor({ ...editor, googleCalendarId: event.target.value })}>
        <option value="">{text.select}</option>{writable.map(item => <option key={item.id} value={item.id}>{item.summary}</option>)}
      </select>{writable.length === 0 && <small>{text.unavailable}</small>}</label>}
      <div className="calendar-dialog-actions"><button className="calendar-secondary" type="button" onClick={() => setEditor(null)}>{text.cancel}</button>
        {editor.id && selectedEvent && canDeleteCalendarEvent(selectedEvent, canDelete) && <button className="calendar-danger" type="button" onClick={() => void remove()} disabled={saving || selectedEvent?.pendingDeletion}>{text.remove}</button>}
        <button className="calendar-primary" type="submit" disabled={saving || (selectedEvent?.pendingDeletion && editor.syncToGoogle)}>{saving ? text.saving : text.save}</button>
      </div>
      {message && <p ref={editorFeedback} role="alert">{message}</p>}
    </form></div>}
  </section>;
}

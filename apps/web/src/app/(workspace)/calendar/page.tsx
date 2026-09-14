"use client";

import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { browserRequest } from "@/lib/browser-request";
import { useEffect, useState } from "react";

type CalendarEvent = { id: string; summary: string; start: string | null; end: string | null };

export default function CalendarPage() {
  const { t } = useWorkspace();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const month = new Date(); const first = new Date(month.getFullYear(), month.getMonth(), 1); const days = Array.from({ length: new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate() }, (_, index) => index + 1); const offset = (first.getDay() + 6) % 7;
  useEffect(() => { void browserRequest("/api/integrations/google/calendar/events", { cache: "no-store" }).then(async (response) => { const value: unknown = await response.json(); if (!response.ok || !value || typeof value !== "object" || !Array.isArray((value as { items?: unknown }).items)) throw new Error(); setEvents((value as { items: CalendarEvent[] }).items); setState("ready"); }).catch(() => setState("error")); }, []);
  return <section className="plugins-stage integration-detail">
    <header className="plugins-header"><div><h1>{t.calendarTitle}</h1><p>Google Calendar</p></div></header>
    <article className="connection-card calendar-panel"><div className="calendar-toolbar"><h2>{month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h2><button className="catalog-reload" type="button">Heute</button></div><div className="calendar-weekdays">{["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"].map((day) => <span key={day}>{day}</span>)}</div><div className="calendar-grid">{Array.from({ length: offset }).map((_, index) => <span className="calendar-day empty" key={`empty-${index}`} />)}{days.map((day) => { const date = new Date(month.getFullYear(), month.getMonth(), day); const matches = events.filter((event) => event.start && new Date(event.start).toDateString() === date.toDateString()); return <div className={`calendar-day ${date.toDateString() === new Date().toDateString() ? "today" : ""}`} key={day}><span>{day}</span>{matches.map((event) => <button className="calendar-event" key={event.id} type="button" title={event.summary}>{event.summary}</button>)}</div>; })}</div>{state === "loading" && <p role="status">Kalender wird geladen …</p>}{state === "error" && <p role="alert">Termine konnten nicht geladen werden. <Link href="/plugins/google">Google-Verbindung prüfen</Link></p>}{state === "ready" && events.length === 0 && <p>Keine kommenden Termine.</p>}</article>
  </section>;
}

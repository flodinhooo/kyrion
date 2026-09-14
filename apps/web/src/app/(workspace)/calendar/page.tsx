"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import { useWorkspace } from "@/components/app-shell";
import { browserRequest } from "@/lib/browser-request";

type CalendarEvent = { id: string; title: string; startsAt: string; endsAt: string };

export default function CalendarPage() {
  const { t } = useWorkspace();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    void browserRequest("/api/calendar/events", { cache: "no-store" }).then(async (response) => {
      const value: unknown = await response.json();
      if (!response.ok || !value || typeof value !== "object" || !Array.isArray((value as { items?: unknown }).items)) throw new Error();
      setEvents((value as { items: CalendarEvent[] }).items);
      setState("ready");
    }).catch(() => setState("error"));
  }, []);

  const calendarEvents = events.map((event) => ({
    id: event.id, title: event.title, start: event.startsAt, end: event.endsAt,
  }));

  return <section className="plugins-stage integration-detail calendar-page">
    <header className="plugins-header"><div><h1>{t.calendarTitle}</h1><p>Google Calendar</p></div><Link className="catalog-reload" href="/plugins/google">Verbindungen</Link></header>
    <article className="connection-card calendar-panel">
      <FullCalendar plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]} initialView="dayGridMonth" firstDay={1} height="auto" expandRows headerToolbar={{ left: "prev,next today", center: "title", right: "dayGridMonth,timeGridWeek,timeGridDay" }} buttonText={{ today: "Heute", month: "Monat", week: "Woche", day: "Tag" }} events={calendarEvents} />
      {state === "loading" && <p role="status">Kalender wird geladen ...</p>}
      {state === "error" && <p role="alert">Termine konnten nicht geladen werden. <Link href="/plugins/google">Google-Verbindung prüfen</Link></p>}
      {state === "ready" && events.length === 0 && <p>Keine kommenden Termine.</p>}
    </article>
  </section>;
}

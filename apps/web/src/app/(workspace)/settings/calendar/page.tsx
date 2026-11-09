"use client";

import Link from "next/link";
import {useEffect, useState} from "react";
import {useWorkspace} from "@/components/app-shell";
import {browserRequest} from "@/lib/browser-request";
import {calendarMessages} from "@/features/calendar/messages";
import {CalendarSyncSettings, type CalendarSchedule} from "@/features/calendar/sync-settings";
import {PersonalCalendarDisclosure} from "@/features/calendar/personal-disclosure";
import {HouseholdDestination} from "@/features/calendar/household-destination";

type Calendar = { id: string; summary: string; accessRole: string };

function calendarsFrom(value: unknown): Calendar[] | null {
  if (!value || typeof value !== "object" || !("items" in value) || !Array.isArray(value.items)) return null;
  return value.items.every((item): item is Calendar => !!item && typeof item === "object" &&
    typeof item.id === "string" && typeof item.summary === "string" && typeof item.accessRole === "string") ? value.items : null;
}

export default function CalendarSettingsPage() {
  const {locale, permissions} = useWorkspace();
  const text = calendarMessages[locale] ?? calendarMessages.en;
  const [schedule, setSchedule] = useState<CalendarSchedule | null>(null);
  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [error, setError] = useState(false);
  const canUpdate = permissions.includes("calendar:update");
  const canCreate = permissions.includes("calendar:create");
  const canSync = canCreate && canUpdate && permissions.includes("calendar:delete");
  useEffect(() => {
    const controller = new AbortController();
    void browserRequest("/api/integrations/google/calendar/calendars", {cache: "no-store", signal: controller.signal})
      .then(async response => response.ok ? calendarsFrom(await response.json()) : null)
      .then(items => {
        if (!controller.signal.aborted) {
          setCalendars(items ?? []);
          setError(items === null);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => controller.abort();
  }, []);
  return <section className="plugins-stage integration-detail calendar-page calendar-settings">
    <header className="plugins-header">
      <div><h1>{text.settingsTitle}</h1><p>{text.settingsDescription}</p></div>
      <div className="calendar-actions"><Link className="calendar-secondary"
                                              href="/calendar">{text.backToCalendar}</Link><Link
        className="calendar-secondary" href="/plugins/google">{text.googleSettings}</Link></div>
    </header>
    {error && <p role="alert">{text.googleError}</p>}
    <PersonalCalendarDisclosure locale={locale} canUpdate={canUpdate} calendars={calendars}/>
    <HouseholdDestination locale={locale} canUpdate={canUpdate} canEnable={canCreate && canUpdate}
                          calendars={calendars}/>
    {canSync && <CalendarSyncSettings schedule={schedule} onChange={setSchedule}/>}
  </section>;
}

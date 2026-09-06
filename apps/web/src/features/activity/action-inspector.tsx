"use client";

import { useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { isActivityResponse, type ActivityEvent } from "./contracts";
import { timelineMessages } from "./timeline-messages";
import { executionDuration } from "./timeline";
import { isActionOutcome, type ActionOutcome } from "@/features/actions/contracts";

export function ActionInspector({ correlationId }: { correlationId: string }) {
  const { locale } = useWorkspace();
  const t = timelineMessages[locale] ?? timelineMessages.en;
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<ActivityEvent[] | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [error, setError] = useState(false);
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    void fetch(`/api/activity/timeline/${encodeURIComponent(correlationId)}`, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        const body: unknown = await response.json();
        if (!response.ok || !isActivityResponse(body) || !("truncated" in body) || typeof body.truncated !== "boolean") throw new Error("Invalid timeline");
        const result = "outcome" in body ? body.outcome : null;
        if (result !== null && !isActionOutcome(result)) throw new Error("Invalid outcome");
        setOutcome(result);
        setEvents(body.items); setTruncated(body.truncated); setError(false);
      }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [open, correlationId]);
  const duration = events ? executionDuration(events, truncated) : null;
  return <details className="action-inspector" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary>{t.inspect}</summary>
    {open && <section aria-label={t.title}>
      <p>{t.correlation}: <code>{correlationId}</code></p>
      {error ? <p role="alert">{t.error}</p> : events === null ? <p>{t.loading}</p> : <>
        <p>{duration === null ? t.incomplete : `${t.duration}: ${duration} ms`}</p>
        {outcome && <p>{t.requested}: {outcome.requested} · {t.succeeded}: {outcome.succeeded} · {t.failed}: {outcome.failed}</p>}
        {truncated && <p>{t.truncated}</p>}
        {events.length === 0 && <p>{t.empty}</p>}
        <ol className="action-timeline">{events.map((event) => <li className="action-timeline-step" key={event.id}>
          <div className="activity-card-content">
            <time dateTime={event.occurredAt}>{new Intl.DateTimeFormat(locale, { timeStyle: "medium" }).format(new Date(event.occurredAt))}</time>
            <strong>{t.stages[event.eventType as keyof typeof t.stages] ?? t.stages["activity.recorded"]}</strong>
            <p>{outcome?.targets.find((target) => target.targetId === event.summaryCode)?.displayName ?? t.reasons[event.summaryCode as keyof typeof t.reasons] ?? event.summaryCode}</p>
            <small>{t.source}: {event.source} · {t.actor}: {event.actorId ?? event.actorType}</small>
          </div>
        </li>)}</ol>
      </>}
    </section>}
  </details>;
}

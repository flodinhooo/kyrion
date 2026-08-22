"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";
import { ActivityEvent, ActivityIntegrityResponse, isActivityIntegrityResponse, isActivityResponse } from "@/features/activity/contracts";

type LoadingState = "loading" | "ready" | "error";

export default function ActivityPage() {
  const { locale, t } = useWorkspace();
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [state, setState] = useState<LoadingState>("loading");
  const [integrity, setIntegrity] = useState<ActivityIntegrityResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadActivity() {
      try {
        const [response, integrityResponse] = await Promise.all([
          fetch("/api/activity", { cache: "no-store", signal: controller.signal }),
          fetch("/api/activity/integrity", { cache: "no-store", signal: controller.signal }),
        ]);
        const body: unknown = await response.json(); const integrityBody: unknown = await integrityResponse.json();
        if (!response.ok || !isActivityResponse(body) || !integrityResponse.ok || !isActivityIntegrityResponse(integrityBody)) throw new Error("Activity unavailable");
        setEvents(body.items);
        setIntegrity(integrityBody);
        setState("ready");
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("error");
      }
    }
    void loadActivity();
    return () => controller.abort();
  }, []);

  const dateFormatter = new Intl.DateTimeFormat(locale === "de" ? "de-CH" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "medium",
  });

  const summary = (event: ActivityEvent) => ({
    "activity.core.started": t.activityCoreStarted,
    "activity.auth.sessionRevoked": t.activitySessionRevoked,
    "memory.enabled": t.activityMemoryEnabled,
    "memory.disabled": t.activityMemoryDisabled,
    "memory.proposed": t.activityMemoryProposed,
    "memory.confirmed": t.activityMemoryConfirmed,
    "memory.updated": t.activityMemoryUpdated,
    "memory.deleted": t.activityMemoryDeleted,
    "memory.replaced": t.activityMemoryReplaced,
  })[event.summaryCode] ?? event.eventType;

  const statusLabel = (status: ActivityEvent["status"]) => ({
    PROPOSED: t.activityStatusProposed,
    CONFIRMED: t.activityStatusConfirmed,
    SUCCEEDED: t.activityStatusSucceeded,
    FAILED: t.activityStatusFailed,
    DENIED: t.activityStatusDenied,
  })[status];

  return (
    <section className="activity-stage">
      <header className="activity-header">
        <div>
          <p className="eyebrow">Kyrion Core</p>
          <h1>{t.activityTitle}</h1>
          <p>{t.activityDescription}</p>
        </div>
      </header>

      {state === "loading" && <div className="activity-loading">{t.activityLoading}</div>}

      {state === "ready" && integrity && <div className={`activity-integrity ${integrity.owner.valid && integrity.system.valid ? "activity-integrity-valid" : "activity-integrity-invalid"}`} role="status">
        <strong>{integrity.owner.valid && integrity.system.valid ? t.activityIntegrityValid : t.activityIntegrityInvalid}</strong>
        <span>{t.activityIntegritySealed}: {integrity.owner.sealedEvents + integrity.system.sealedEvents}</span>
        {(integrity.owner.legacyEvents + integrity.system.legacyEvents) > 0 && <span>{t.activityIntegrityLegacy}: {integrity.owner.legacyEvents + integrity.system.legacyEvents}</span>}
      </div>}

      {state === "error" && <div className="activity-empty">
        <span className="activity-empty-icon"><Icons.activity /></span>
        <h2>{t.activityUnavailableTitle}</h2>
        <p>{t.activityUnavailableDescription}</p>
      </div>}

      {state === "ready" && events.length === 0 && <div className="activity-empty">
        <span className="activity-empty-icon"><Icons.activity /></span>
        <h2>{t.activityEmptyTitle}</h2>
        <p>{t.activityEmptyDescription}</p>
        <div className="activity-principles">
          <span>{t.activityPrincipleTraceable}</span>
          <span>{t.activityPrinciplePrivate}</span>
          <span>{t.activityPrincipleConfirmed}</span>
        </div>
        <Link className="placeholder-action" href="/">{t.backToChat}</Link>
      </div>}

      {state === "ready" && events.length > 0 && <ol className="activity-list">
        {events.map((event) => <li className="activity-card" key={event.id}>
          <span className={`activity-marker activity-marker-${event.status.toLowerCase()}`} aria-hidden="true" />
          <div className="activity-card-content">
            <div className="activity-card-heading">
              <div>
                <p className="activity-summary">{summary(event)}</p>
                <p className="activity-source">{event.source} · {event.category.toLowerCase()}</p>
              </div>
              <span className={`activity-status activity-status-${event.status.toLowerCase()}`}>
                {statusLabel(event.status)}
              </span>
            </div>
            <time dateTime={event.occurredAt}>{dateFormatter.format(new Date(event.occurredAt))}</time>
            <code title={t.activityCorrelationId}>{event.correlationId}</code>
          </div>
        </li>)}
      </ol>}
    </section>
  );
}

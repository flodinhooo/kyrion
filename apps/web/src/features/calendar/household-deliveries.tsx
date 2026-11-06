"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { browserRequest } from "@/lib/browser-request";
import { csrfHeader } from "@/features/auth/csrf";
import { calendarMessages } from "./messages";
import { deliveryView, type DeliveryView, type DeliveryState } from "./delivery-model";

export function HouseholdDeliveriesPanel({ eventId, revision, dirty, disabled, locale, onBusyChange }: {
  eventId: string; revision: number; dirty: boolean; disabled: boolean; locale: "de" | "en";
  onBusyChange: (busy: boolean) => void;
}) {
  const text = calendarMessages[locale] ?? calendarMessages.en;
  const [view, setView] = useState<DeliveryView | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const active = useRef(true);
  const url = `/api/calendar/household-events/${encodeURIComponent(eventId)}/deliveries`;
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await browserRequest(url, { cache: "no-store", signal });
      const current = response.ok ? deliveryView(await response.json()) : null;
      if (!active.current || signal?.aborted) return;
      if (!current || current.revision !== revision) { setView(null); return; }
      setView(current); setSelected(previous => previous.filter(id => current.targets.some(target => target.targetId === id)));
    } catch { if (active.current && !signal?.aborted) setView(null); }
  }, [url, revision]);
  useEffect(() => {
    active.current = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => { active.current = false; controller.abort(); window.clearTimeout(timer); onBusyChange(false); };
  }, [load, onBusyChange]);
  async function publish() {
    if (!view || dirty || busy || selected.length === 0) return;
    const targets = view.targets.filter(item => item.targetId && selected.includes(item.targetId));
    if (!window.confirm(`${text.deliveryConfirm}\n${targets.map(item => item.username).join(", ")}`)) return;
    setBusy(true); onBusyChange(true); setMessage(null);
    let interrupted = false;
    try {
      for (const target of targets) {
        if (!active.current) return;
        try {
          const response = await browserRequest(url, { method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() },
            signal: AbortSignal.timeout(115_000),
            body: JSON.stringify({ targetId: target.targetId, revision }) });
          if (!response.ok) interrupted = true;
          if ([401, 403, 409].includes(response.status)) break;
        } catch { interrupted = true; break; }
        if (active.current) await load();
      }
      if (active.current) { await load(); setMessage(interrupted ? text.deliveryInterrupted : text.deliveryResult); }
    } finally { if (active.current) { setBusy(false); onBusyChange(false); } }
  }
  const states: Record<DeliveryState, string> = { RUNNING: text.deliveryStateRunning, SYNCED: text.deliveryStateSynced,
    OUTDATED: text.deliveryStateOutdated, ERROR: text.deliveryStateError, CONFLICT: text.deliveryStateConflict,
    BLOCKED: text.deliveryStateBlocked, NEEDS_REVIEW: text.deliveryStateReview };
  return <fieldset><legend>{text.deliveryTitle}</legend><p>{text.deliverySaveFirst}</p>
    {view === null ? <p role="status">{text.deliveryUnavailable}</p> : <>
      <button className="calendar-secondary" type="button" disabled={busy || disabled} onClick={() => setSelected(view.targets.flatMap(item => item.targetId ? [item.targetId] : []))}>{text.selectEveryone}</button>
      {view.targets.map(target => <label className="calendar-checkbox" key={target.userId}><input type="checkbox" checked={!!target.targetId && selected.includes(target.targetId)}
        disabled={!target.targetId || busy || disabled} onChange={event => { const id = target.targetId; if (id) setSelected(previous => event.target.checked ? [...previous, id] : previous.filter(item => item !== id)); }} />
        {target.username}{!target.targetId && ` · ${text.deliveryMissing}`}</label>)}
      {view.items.map(item => <p key={item.id}>{item.username ?? text.formerParticipant}: {item.errorCode === "CALENDAR_DELIVERY_PROVIDER_DENIED" ? text.deliveryProviderDenied : item.errorCode === "GOOGLE_RATE_LIMITED" ? text.deliveryRateLimited : states[item.state]}
        {item.deliveredRevision !== null && ` · ${text.deliveryRevision}: ${item.deliveredRevision}`}</p>)}
      <button className="calendar-primary" type="button" disabled={busy || disabled || dirty || selected.length === 0} onClick={() => void publish()}>{busy ? text.deliverySending : text.deliverySend}</button>
    </>}
    <button className="calendar-secondary" type="button" disabled={busy || disabled} onClick={() => void load()}>{text.deliveryRefresh}</button>
    {message && <p role="status">{message}</p>}
  </fieldset>;
}

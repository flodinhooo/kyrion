"use client";

import { useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import { isRetentionPolicy, RetentionPeriod, RetentionPolicy, retentionPeriods } from "@/features/retention/contracts";

export function RetentionPolicyPanel() {
  const { t } = useWorkspace();
  const [policy, setPolicy] = useState<RetentionPolicy | null>(null);
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  useEffect(() => {
    let disposed = false;
    void fetch("/api/retention", { cache: "no-store" }).then(async response => {
      const value: unknown = await response.json();
      if (!response.ok || !isRetentionPolicy(value)) throw new Error("Invalid retention policy");
      if (!disposed) setPolicy(value);
    }).catch(() => { if (!disposed) setState("error"); });
    return () => { disposed = true; };
  }, []);
  const change = (key: "conversations" | "activity" | "personalMemory", value: RetentionPeriod) =>
    setPolicy(current => current ? { ...current, [key]: value } : current);
  async function save() {
    if (!policy) return; setState("saving");
    try {
      const response = await fetch("/api/retention", { method: "PUT", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify(policy) });
      const value: unknown = await response.json();
      if (!response.ok || !isRetentionPolicy(value)) throw new Error("Retention update failed");
      setPolicy(value); setState("saved");
    } catch { setState("error"); }
  }
  const labels: Record<RetentionPeriod, string> = {
    keep_forever: t.retentionForever, "30_days": t.retention30Days, "90_days": t.retention90Days,
    "365_days": t.retention365Days, "3_years": t.retention3Years,
  };
  return <div className="settings-link-card retention-panel">
    <strong>{t.retentionTitle}</strong><small>{t.retentionDescription}</small>
    {!policy && state !== "error" && <p>{t.retentionLoading}</p>}
    {policy && <div className="retention-fields">
      {(["conversations", "activity", "personalMemory"] as const).map(key => <label key={key}>
        {key === "conversations" ? t.retentionConversations : key === "activity" ? t.retentionActivity : t.retentionMemory}
        <select value={policy[key]} onChange={event => change(key, event.target.value as RetentionPeriod)}>
          {retentionPeriods.map(period => <option key={period} value={period}>{labels[period]}</option>)}
        </select>
      </label>)}
      <p className="retention-notice">{t.retentionNotEnforced}</p>
      <button type="button" disabled={state === "saving"} onClick={() => void save()}>{state === "saving" ? t.retentionSaving : t.retentionSave}</button>
    </div>}
    {state === "saved" && <p className="form-success" role="status">{t.retentionSaved}</p>}
    {state === "error" && <p className="auth-error" role="alert">{t.retentionError}</p>}
  </div>;
}

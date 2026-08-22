"use client";

import { useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import { isRetentionCleanupPreview, isRetentionPolicy, RetentionCleanupPreview, RetentionPeriod, RetentionPolicy, retentionPeriods } from "@/features/retention/contracts";

export function RetentionPolicyPanel() {
  const { t } = useWorkspace();
  const [policy, setPolicy] = useState<RetentionPolicy | null>(null);
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [cleanupState, setCleanupState] = useState<"idle" | "working" | "complete" | "error">("idle");
  const [preview, setPreview] = useState<RetentionCleanupPreview | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [deleted, setDeleted] = useState<{conversationsDeleted:number;activityDeleted:number;personalMemoriesDeleted:number}|null>(null);
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
      setPolicy(value); setPreview(null); setConfirmation(""); setDeleted(null); setState("saved");
    } catch { setState("error"); }
  }
  async function loadPreview() {
    setCleanupState("working"); setPreview(null); setDeleted(null); setConfirmation("");
    try {
      const response = await fetch("/api/retention/preview", { cache: "no-store" }); const value: unknown = await response.json();
      if (!response.ok || !isRetentionCleanupPreview(value)) throw new Error("Retention preview failed");
      setPreview(value); setCleanupState("idle");
    } catch { setCleanupState("error"); }
  }
  async function cleanup() {
    if (confirmation !== "DELETE") return; setCleanupState("working");
    try {
      const response = await fetch("/api/retention/cleanup", { method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify({ confirmation }) });
      const value = await response.json() as {conversationsDeleted?:unknown;activityDeleted?:unknown;personalMemoriesDeleted?:unknown};
      if (!response.ok || typeof value.conversationsDeleted !== "number" || typeof value.activityDeleted !== "number" || typeof value.personalMemoriesDeleted !== "number") throw new Error("Retention cleanup failed");
      setDeleted(value as {conversationsDeleted:number;activityDeleted:number;personalMemoriesDeleted:number}); setPreview(null); setConfirmation(""); setCleanupState("complete");
    } catch { setCleanupState("error"); }
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
      <button type="button" disabled={cleanupState === "working"} onClick={() => void loadPreview()}>{cleanupState === "working" ? t.retentionPreviewLoading : t.retentionPreview}</button>
    </div>}
    {preview && <div className="retention-cleanup-preview"><strong>{t.retentionPreviewTitle}</strong>
      <span>{t.retentionConversations}: {preview.conversations.records}</span><span>{t.retentionActivity}: {preview.activity.records}</span><span>{t.retentionMemory}: {preview.personalMemory.records}</span>
      <p>{t.retentionCleanupWarning}</p><label>{t.retentionCleanupConfirmation}<input value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="off" /></label>
      <button type="button" disabled={confirmation !== "DELETE" || cleanupState === "working"} onClick={() => void cleanup()}>{t.retentionCleanup}</button>
    </div>}
    {deleted && <p className="form-success" role="status">{t.retentionCleanupComplete} {t.retentionConversations}: {deleted.conversationsDeleted}, {t.retentionActivity}: {deleted.activityDeleted}, {t.retentionMemory}: {deleted.personalMemoriesDeleted}</p>}
    {state === "saved" && <p className="form-success" role="status">{t.retentionSaved}</p>}
    {(state === "error" || cleanupState === "error") && <p className="auth-error" role="alert">{t.retentionError}</p>}
  </div>;
}

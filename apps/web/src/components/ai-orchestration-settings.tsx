"use client";

import {useCallback, useEffect, useState} from "react";
import {useWorkspace} from "@/components/app-shell";
import {csrfHeader} from "@/features/auth/csrf";
import {
  isAiSettings,
  isAiUsage,
  type AiSettings,
  type AiUsage,
  type AiPreferences,
  type AiPolicy
} from "@/features/models/orchestration-contracts";
import {orchestrationMessages} from "@/features/models/orchestration-messages";

export function AiOrchestrationSettings() {
  const {locale, modelCatalog, selectModel} = useWorkspace();
  const t = orchestrationMessages[locale];
  const [settings, setSettings] = useState<AiSettings | null>(null);
  const [usage, setUsage] = useState<AiUsage | null>(null);
  const [status, setStatus] = useState<"" | "saved" | "error">("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const [a, b] = await Promise.all([fetch("/api/ai/preferences", {
        signal,
        cache: "no-store"
      }), fetch("/api/ai/usage", {signal, cache: "no-store"})]);
      const preferences: unknown = await a.json(), stats: unknown = await b.json();
      if (!a.ok || !b.ok || !isAiSettings(preferences) || !isAiUsage(stats)) throw new Error("Invalid AI settings");
      setSettings(preferences);
      setUsage(stats);
    } catch {
      if (!signal?.aborted) setStatus("error");
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.resolve().then(() => {
      if (!controller.signal.aborted) return load(controller.signal);
    });
    return () => controller.abort();
  }, [load]);

  async function save(operation: "preferences" | "policy") {
    if (!settings) return;
    setBusy(true);
    setStatus("");
    try {
      const response = await fetch(`/api/ai/${operation}`, {
        method: "PUT",
        headers: {"Content-Type": "application/json", ...csrfHeader()},
        body: JSON.stringify(settings[operation])
      });
      if (!response.ok) throw new Error("Settings refused");
      setStatus("saved");
      await load();
    } catch {
      setStatus("error");
    } finally {
      setBusy(false);
    }
  }

  function preference(patch: Partial<AiPreferences>) {
    setSettings(old => old ? {...old, preferences: {...old.preferences, ...patch}} : old);
  }

  function policy(patch: Partial<AiPolicy>) {
    setSettings(old => old ? {...old, policy: {...old.policy, ...patch}} : old);
  }

  const models = modelCatalog?.models ?? [];
  const providers = ["ollama", "openai", "anthropic", "gemini"];
  const list = (raw: string) => [...new Set(raw.split(",").map(value => value.trim()).filter(Boolean))];
  const toggle = (values: string[], id: string) => values.includes(id) ? values.filter(value => value !== id) : [...values, id];
  if (!settings) return <section className="settings-card"><h2>{t.title}</h2>{status === "error" &&
    <p role="alert">{t.error}</p>}</section>;
  const p = settings.preferences, a = settings.policy;
  return <section className="settings-card">
    <h2>{t.title}</h2><p>{t.privacy}</p>
    <button type="button" onClick={() => selectModel("auto")}>{t.automatic}</button>
    <div className="model-grid">
      <label>{t.chat}<select value={p.chatProfileId ?? ""}
                             onChange={e => preference({chatProfileId: e.target.value || null})}>
        <option value="">{t.automatic}</option>
        {models.map(m => <option key={m.id} value={m.id}>{m.provider} / {m.label}</option>)}</select></label>
      <label>{t.voice}<select value={p.voiceProfileId ?? ""}
                              onChange={e => preference({voiceProfileId: e.target.value || null})}>
        <option value="">{t.automatic}</option>
        {models.filter(m => m.local !== false).map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
      </select></label>
      <label>{t.provider}<select value={p.preferredProvider ?? ""}
                                 onChange={e => preference({preferredProvider: e.target.value || null})}>
        <option value="">{t.automatic}</option>
        {providers.map(id => <option key={id}>{id}</option>)}</select></label>
      <label><input type="checkbox" checked={p.localOnly}
                    onChange={e => preference({localOnly: e.target.checked})}/>{t.localOnly}</label>
      <fieldset>
        <legend>{t.clouds}</legend>
        {providers.filter(id => id !== "ollama").map(id => <label key={id}><input type="checkbox"
                                                                                  checked={p.allowedCloudProviders.includes(id)}
                                                                                  onChange={() => preference({allowedCloudProviders: toggle(p.allowedCloudProviders, id)})}/>{id}
        </label>)}</fieldset>
      <label>{t.preference}<select value={p.routingPreference}
                                   onChange={e => preference({routingPreference: e.target.value})}>
        <option value="local_first">{t.localFirst}</option>
        <option value="economy">{t.economy}</option>
      </select></label>
      <label><input type="checkbox" checked={p.allowFallback}
                    onChange={e => preference({allowFallback: e.target.checked})}/>{t.fallback}</label>
      <label>{t.limit}<input type="number" min="1" value={p.monthlyTokenLimit ?? ""}
                             onChange={e => preference({monthlyTokenLimit: e.target.value ? Number(e.target.value) : null})}/></label>
    </div>
    <button type="button" disabled={busy} onClick={() => void save("preferences")}>{t.save}</button>
    <p>{t.fallbackNote}</p>
    {settings.canAdmin && <details>
      <summary>{t.admin}</summary>
      <div className="model-grid">
        <fieldset>
          <legend>{t.providers}</legend>
          {providers.map(id => <label key={id}><input type="checkbox" checked={a.allowedProviders.includes(id)}
                                                      onChange={() => policy({allowedProviders: toggle(a.allowedProviders, id)})}/>{id}
          </label>)}</fieldset>
        <label><input type="checkbox" checked={a.allowCloud}
                      onChange={e => policy({allowCloud: e.target.checked})}/>{t.cloud}</label>
        <label><input type="checkbox" checked={a.allowUserSelection}
                      onChange={e => policy({allowUserSelection: e.target.checked})}/>{t.selection}</label>
        <label>{t.models}<select multiple value={a.allowedProfiles}
                                 onChange={e => policy({allowedProfiles: Array.from(e.target.selectedOptions, o => o.value)})}>{models.map(m =>
          <option key={m.id} value={m.id}>{m.label}</option>)}</select></label>
        <label>{t.priorities}<input value={a.priorities.join(", ")}
                                    onChange={e => policy({priorities: list(e.target.value)})}/></label>
        <label><input type="checkbox" checked={a.allowFallback}
                      onChange={e => policy({allowFallback: e.target.checked})}/>{t.fallback}</label>
        <label>{t.fallbackModels}<select multiple value={a.fallbackProfiles}
                                         onChange={e => policy({fallbackProfiles: Array.from(e.target.selectedOptions, o => o.value)})}>{models.map(m =>
          <option key={m.id} value={m.id}>{m.provider} / {m.label}</option>)}</select></label>
        {(["monthlyTokenLimit", "monthlyCostLimit", "maxRequestTokens", "maxTimeoutSeconds"] as const).map((key, i) =>
          <label key={key}>{[t.tokens, t.cost, t.requestLimit, t.timeout][i]}<input type="number" min="0"
                                                                                    step={key === "monthlyCostLimit" ? "any" : "1"}
                                                                                    value={a[key] ?? ""}
                                                                                    onChange={e => policy({[key]: e.target.value ? Number(e.target.value) : null})}/></label>)}
        <label>{t.currency}<input maxLength={3} value={a.currency ?? ""}
                                  onChange={e => policy({currency: e.target.value.toUpperCase() || null})}/></label>
        <fieldset>
          <legend>{t.task}</legend>
          {["chat", "voice", "analysis", "code", "tools"].map(task => <label
            key={task}>{t.taskNames[task as keyof typeof t.taskNames]}<input
            value={a.taskProfiles[task]?.join(", ") ?? ""}
            onChange={e => policy({taskProfiles: {...a.taskProfiles, [task]: list(e.target.value)}})}/></label>)}
        </fieldset>
      </div>
      <button type="button" disabled={busy} onClick={() => void save("policy")}>{t.save}</button>
    </details>}
    <h3>{t.usage} {usage?.period}</h3><p>{t.budgetNote}</p>
    <button type="button" onClick={() => void load()}>{t.refresh}</button>
    {usage && <>
      <p>{t.charged}: {usage.chargedTokens.toLocaleString(locale)} / {usage.tokenLimit?.toLocaleString(locale) ?? "—"}</p>
      <p>{t.estimate}: {usage.costLimit ?? "—"} {usage.currency ?? ""}</p>
      <div className="table-wrap">
        <table>
          <thead>
          <tr>{[t.provider, t.requests, t.charged, t.input, t.output, t.estimate, t.pending].map(label => <th
            key={label}>{label}</th>)}</tr>
          </thead>
          <tbody>{usage.rows.map((row, i) => <tr key={`${row.profileId}:${i}`}>
            <td>{row.provider} / {row.profileId}</td>
            <td>{row.requests}</td>
            <td>{row.chargedTokens}</td>
            <td>{row.inputTokens ?? "—"}</td>
            <td>{row.outputTokens ?? "—"}</td>
            <td>{row.estimatedCost ?? "—"} {row.currency}</td>
            <td>{row.pending}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </>}
    {status && <p role={status === "error" ? "alert" : "status"}>{status === "error" ? t.error : t.saved}</p>}
  </section>;
}

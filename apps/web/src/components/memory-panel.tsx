"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import {ContextSourceInspector} from "@/components/context-source-inspector";
import {contextMessages} from "@/features/memory/context-messages";
import { csrfHeader } from "@/features/auth/csrf";
import type { MemoryCategory, MemoryProfile, MemorySensitivity, PersonalMemory } from "@/features/memory/contracts";
import { isMemoryProfile } from "@/features/memory/contracts";

export function MemoryPanel() {
  const {t, locale} = useWorkspace();
  const c = contextMessages[locale];
  const [profile, setProfile] = useState<MemoryProfile | null>(null);
  const [error, setError] = useState(false);
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/memory", { cache: "no-store" });
      const value: unknown = await response.json();
      if (!response.ok || !isMemoryProfile(value)) throw new Error("Invalid memory profile");
      setProfile(value); setError(false);
    } catch { setError(true); }
  }, []);

  useEffect(() => {
    let disposed = false;
    void fetch("/api/memory", { cache: "no-store" }).then(async (response) => {
      const value: unknown = await response.json();
      if (!response.ok || !isMemoryProfile(value)) throw new Error("Invalid memory profile");
      if (!disposed) { setProfile(value); setError(false); }
    }).catch(() => { if (!disposed) setError(true); });
    return () => { disposed = true; };
  }, []);

  async function setEnabled(enabled: boolean) {
    setPending(true);
    try {
      const response = await fetch("/api/memory/settings", {
        method: "PUT", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({ enabled }),
      });
      if (!response.ok) throw new Error("Memory setting failed");
      await load();
    } catch { setError(true); } finally { setPending(false); }
  }

  async function propose(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget; const data = new FormData(form); setPending(true);
    try {
      const response = await fetch("/api/memory", {
        method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({ category: data.get("category"), content: data.get("content"), sensitivity: data.get("sensitivity") }),
      });
      if (!response.ok) throw new Error("Memory proposal failed");
      form.reset(); await load();
    } catch { setError(true); } finally { setPending(false); }
  }

  async function confirm(id: string, resolution: "keep" | "replace" = "keep") { await mutate(`/api/memory/${id}/confirm?resolution=${resolution}`, "POST"); }

  async function forget(id: string) {
    const proposed = profile?.items.find(item => item.id === id)?.status === "proposed";
    await mutate(`/api/memory/${id}${proposed ? "/reject" : ""}`, proposed ? "POST" : "DELETE");
  }
  async function update(id: string, category: MemoryCategory, content: string, sensitivity: MemorySensitivity) {
    await mutate(`/api/memory/${id}`, "PATCH", { category, content, sensitivity });
  }

  async function mutate(url: string, method: "POST" | "PATCH" | "DELETE" | "PUT", body?: object) {
    setPending(true);
    try {
      const response = await fetch(url, {
        method, headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...csrfHeader() },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok) throw new Error("Memory mutation failed");
      await load();
    } catch { setError(true); } finally { setPending(false); }
  }

  return (
    <div className="settings-link-card memory-panel">
      <div className="memory-heading">
        <span><strong>{t.memoryTitle}</strong><small>{t.memoryDescription}</small></span>
        <button type="button" disabled={pending || !profile} onClick={() => void setEnabled(!profile?.settings.enabled)}>
          {profile?.settings.enabled ? t.memoryDisable : t.memoryEnable}
        </button>
      </div>
      {error && <p className="auth-error" role="alert">{t.memoryError}</p>}
      {profile?.settings.enabled && (
        <form className="memory-form" onSubmit={propose}>
          <label>{t.memoryStatement}<textarea name="content" maxLength={1000} required /></label>
          <label>{t.memoryCategory}<select name="category" defaultValue="preference"><CategoryOptions t={t} /></select></label>
          <label>{t.memorySensitivity}<select name="sensitivity" defaultValue="standard"><option value="standard">{t.memoryStandard}</option><option value="sensitive">{t.memorySensitive}</option></select></label>
          <button type="submit" disabled={pending}>{t.memoryPropose}</button>
        </form>
      )}
      {profile && <fieldset>
        <legend>{c.title}</legend>
        <p>{c.privacy}</p>
        {(["historyEnabled", "preferencesEnabled", "kyrionDataEnabled"] as const).map(key => <label key={key}>
          <input type="checkbox" disabled={pending} checked={profile.settings[key] ?? false}
                 onChange={e => void mutate("/api/memory/context-settings", "PUT", {
                   kyrionDataEnabled: profile.settings.kyrionDataEnabled ?? false,
                   historyEnabled: profile.settings.historyEnabled ?? false,
                   preferencesEnabled: profile.settings.preferencesEnabled ?? false,
                   categories: profile.settings.categories ?? ["preference", "person", "project", "value", "other"],
                   [key]: e.target.checked,
                 })}/>{key === "historyEnabled" ? c.history : key === "preferencesEnabled" ? c.preferences : c.data}
        </label>)}
        <p>{c.categories}</p>{(["preference", "person", "project", "value", "other"] as const).map(category => <label
        key={category}>
        <input type="checkbox" disabled={pending}
               checked={(profile.settings.categories ?? ["preference", "person", "project", "value", "other"]).includes(category)}
               onChange={e => {
                 const current = profile.settings.categories ?? ["preference", "person", "project", "value", "other"];
                 void mutate("/api/memory/context-settings", "PUT", {
                   kyrionDataEnabled: profile.settings.kyrionDataEnabled ?? false,
                   historyEnabled: profile.settings.historyEnabled ?? false,
                   preferencesEnabled: profile.settings.preferencesEnabled ?? false,
                   categories: e.target.checked ? [...current, category] : current.filter(value => value !== category),
                 });
               }}/>{({
        preference: t.memoryPreference,
        person: t.memoryPerson,
        project: t.memoryProject,
        value: t.memoryValue,
        other: t.memoryOther
      })[category]}</label>)}</fieldset>}
      <div className="memory-list">
        {profile && profile.items.length === 0 && <p className="placeholder-copy">{t.memoryEmpty}</p>}
        {profile?.items.map((item) => <MemoryItem key={item.id} item={item}
                                                  conflict={profile.items.find((candidate) => candidate.id === item.conflictsWithMemoryId) ?? null}
                                                  pending={pending}
                                                  onValidity={async (id, active, expiresAt) => mutate(`/api/memory/${id}/validity`, "PATCH", {
                                                    active,
                                                    expiresAt
                                                  })} onConfirm={confirm} onForget={forget} onUpdate={update}/>)}
      </div>
    </div>
  );
}

function CategoryOptions({ t }: { t: ReturnType<typeof useWorkspace>["t"] }) {
  return <><option value="preference">{t.memoryPreference}</option><option value="person">{t.memoryPerson}</option><option value="project">{t.memoryProject}</option><option value="value">{t.memoryValue}</option><option value="other">{t.memoryOther}</option></>;
}

function MemoryItem({item, conflict, pending, onValidity, onConfirm, onForget, onUpdate}: {
  onValidity: (id: string, active: boolean, expiresAt: string | null) => Promise<void>;
  item: PersonalMemory; conflict: PersonalMemory | null; pending: boolean;
  onConfirm: (id: string, resolution?: "keep" | "replace") => Promise<void>; onForget: (id: string) => Promise<void>;
  onUpdate: (id: string, category: MemoryCategory, content: string, sensitivity: MemorySensitivity) => Promise<void>;
}) {
  const {t, locale} = useWorkspace();
  const c = contextMessages[locale];
  const [expiry, setExpiry] = useState(item.expiresAt?.slice(0, 16) ?? "");
  const [content, setContent] = useState(item.content);
  const [category, setCategory] = useState(item.category);
  const [sensitivity, setSensitivity] = useState(item.sensitivity);
  return <article className="memory-item">
    <div className="memory-badges"><span>{item.status === "proposed" ? t.memoryProposed : item.status === "superseded" ? t.memorySuperseded : t.memoryConfirmed}</span><span className={sensitivity === "sensitive" ? "sensitive" : ""}>{sensitivity === "sensitive" ? t.memorySensitive : t.memoryStandard}</span></div>
    {conflict && item.status === "proposed" && <p className="memory-conflict">{t.memoryConflict}: “{conflict.content}”</p>}
    <p>{c.source}: {c.explicit} {item.sourceConversationId ?? ""} / {item.sourceMessageId ?? ""}</p>
    {item.sourceConversationId && item.sourceMessageId &&
      <ContextSourceInspector conversationId={item.sourceConversationId} turnId={item.sourceMessageId}/>}
    <p>{c.created}: {item.createdAt} / {c.updated}: {item.updatedAt}</p>
    <label><input type="checkbox" checked={item.active ?? true} disabled={pending}
                  onChange={e => void onValidity(item.id, e.target.checked, item.expiresAt ?? null)}/>{item.active === false ? c.inactive : item.expiresAt && Date.parse(item.expiresAt) <= Date.now() ? c.expired : c.active}
    </label>
    <label>{c.expiry}<input type="datetime-local" value={expiry} onChange={e => setExpiry(e.target.value)}/></label>
    <button type="button" disabled={pending}
            onClick={() => void onValidity(item.id, item.active ?? true, expiry ? `${expiry}:00Z` : null)}>{t.memorySave}</button>
    <textarea value={content} maxLength={1000} onChange={(event) => setContent(event.target.value)} />
    <div className="memory-item-controls">
      <select value={category} onChange={(event) => setCategory(event.target.value as MemoryCategory)}><CategoryOptions t={t} /></select>
      <select value={sensitivity} onChange={(event) => setSensitivity(event.target.value as MemorySensitivity)}><option value="standard">{t.memoryStandard}</option><option value="sensitive">{t.memorySensitive}</option></select>
      <button type="button" disabled={pending || !content.trim()} onClick={() => void onUpdate(item.id, category, content, sensitivity)}>{t.memorySave}</button>
      {item.status === "proposed" && !conflict && <button type="button" disabled={pending} onClick={() => void onConfirm(item.id)}>{t.memoryConfirm}</button>}
      {item.status === "proposed" && conflict && <><button type="button" disabled={pending} onClick={() => void onConfirm(item.id, "replace")}>{t.memoryReplace}</button><button type="button" disabled={pending} onClick={() => void onConfirm(item.id, "keep")}>{t.memoryKeepBoth}</button></>}
      <button className="danger" type="button" disabled={pending}
              onClick={() => void onForget(item.id)}>{item.status === "proposed" ? c.reject : t.memoryForget}</button>
    </div>
  </article>;
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { csrfHeader } from "@/features/auth/csrf";
import { changeHaEntities, isHaPreview, isHaRooms, isHaSelection, isHaSelectionResult, isHaStatus, type HaChoice, type HaPreview, type HaRoom, type HaStatus } from "./home-assistant-contracts";
import { homeAssistantMessages } from "./home-assistant-messages";

async function request(path: string, method = "GET", body?: unknown): Promise<unknown> {
  const response = await fetch(path, { method, cache: "no-store", headers: method === "GET" ? {} : { "Content-Type": "application/json", ...csrfHeader() }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(50000) });
  const value: unknown = await response.json();
  if (!response.ok) {
    const code = value !== null && typeof value === "object" && "code" in value && typeof value.code === "string" ? value.code : "CORE_UNAVAILABLE";
    throw new Error(code);
  }
  return value;
}

export function HomeAssistantConnection() {
  const { locale } = useWorkspace();
  const t = homeAssistantMessages[locale] ?? homeAssistantMessages.en;
  const [status, setStatus] = useState<HaStatus | null>(null);
  const [url, setUrl] = useState("");
  const [token, setToken] = useState("");
  const [credentials, setCredentials] = useState(false);
  const [inventory, setInventory] = useState<HaPreview | null>(null);
  const [choices, setChoices] = useState<HaChoice[]>([]);
  const [rooms, setRooms] = useState<HaRoom[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [confirm, setConfirm] = useState<"apply" | "disconnect" | null>(null);
  const base = "/api/integrations/home-assistant";

  function failure(error: unknown) {
    const code = error instanceof Error ? error.message : "fallback";
    setError(Object.entries(t.errors).find(([key]) => key === code)?.[1] ?? t.errors.fallback);
  }
  async function load() {
    const value = await request(base);
    if (!isHaStatus(value)) throw new Error("HA_INVALID_RESPONSE");
    setStatus(value);
  }
  useEffect(() => {
    let active = true;
    void request(base).then(value => {
      if (!isHaStatus(value)) throw new Error("HA_INVALID_RESPONSE");
      if (active) setStatus(value);
    }).catch(() => { if (active) setError(t.errors.CORE_UNAVAILABLE); });
    return () => { active = false; };
  }, [t.errors.CORE_UNAVAILABLE]);
  async function operate(action: () => Promise<void>) {
    setPending(true); setError(null); setSuccess(false);
    try { await action(); } catch (error) { failure(error); } finally { setPending(false); }
  }
  function invalidate() { setInventory(null); setChoices([]); setSuccess(false); setError(null); }
  async function preview() {
    await operate(async () => {
      const useStored = status?.configured && !credentials;
      const [value, roomValue, selected] = await Promise.all([
        request(`${base}/preview`, useStored ? "GET" : "POST", useStored ? undefined : { baseUrl: url, accessToken: token }),
        request("/api/home/rooms"),
        status?.configured ? request(`${base}/selection`) : Promise.resolve({ revision: 0, devices: [] }),
      ]);
      if (!isHaPreview(value) || !isHaRooms(roomValue) || !isHaSelection(selected)) throw new Error("HA_INVALID_RESPONSE");
      if (value.revision !== selected.revision) throw new Error("selection_conflict");
      setInventory(value); setRooms(roomValue);
      setChoices(selected.devices.flatMap(choice => {
        const source = value.devices.find(source => source.key === choice.key);
        if (!source) return [];
        const current = changeHaEntities(choice, source, choice.entityKeys.filter(key => source.entities.some(entity => entity.key === key)));
        return current.entityKeys.length ? [current] : [];
      }));
    });
  }
  function update(choice: HaChoice) { setChoices(previous => [...previous.filter(item => item.key !== choice.key), choice]); setSuccess(false); }
  async function apply() {
    if (!inventory) return;
    await operate(async () => {
      const value = await request(`${base}/selection`, "POST", { expectedRevision: inventory.revision, devices: choices, ...(status?.configured && !credentials ? {} : { baseUrl: url, accessToken: token }) });
      if (!isHaSelectionResult(value)) throw new Error("HA_INVALID_RESPONSE");
      setToken(""); setCredentials(false); setInventory(null); setChoices([]); setConfirm(null);
      await load();
      if (value.reason !== null) throw new Error("HA_SYNC_FAILED");
      setSuccess(true);
    });
  }
  async function disconnect() {
    await operate(async () => { await request(base, "DELETE"); setToken(""); invalidate(); setConfirm(null); await load(); });
  }

  return <section className="connection-card ha-connection-card" aria-busy={pending}>
    <div className="ha-connection-heading"><h2>{t.title}</h2><span className="integration-kind integration-kind-local">{t.local}</span></div>
    <p>{status?.configured ? status.status === "healthy" && !status.reason ? t.connected : t.saved : t.unconfigured}</p><p>{t.scope}</p>
    {error && <p role="alert" className="auth-error">{error}</p>}{success && <p role="status" className="ha-success">{t.successful}</p>}
    <fieldset disabled={pending} className="ha-connect-form">
      {status?.configured && <label><input type="checkbox" checked={credentials} onChange={event => { setCredentials(event.target.checked); invalidate(); }} />{t.editCredentials}</label>}
      {(!status?.configured || credentials) && <>
        <label>{t.endpoint}<input type="url" placeholder={t.endpointExample} value={url} autoComplete="off" onChange={event => { setUrl(event.target.value); invalidate(); }} /></label>
        <label>{t.token}<input type="password" value={token} autoComplete="off" onChange={event => { setToken(event.target.value); invalidate(); }} /></label><p>{t.credentialsNote}</p>
      </>}
      <button disabled={pending || ((!status?.configured || credentials) && (!url || !token))} onClick={() => void preview()}>{pending ? t.pending : t.preview}</button>
      {status?.configured && <>
        <button onClick={() => void operate(async () => { const value = await request(`${base}/sync`, "POST"); if (!value || typeof value !== "object" || !("reason" in value) || value.reason !== null) throw new Error("HA_SYNC_FAILED"); await load(); })}>{t.sync}</button>
        <button className="danger" onClick={() => setConfirm("disconnect")}>{t.disconnect}</button>
      </>}
      {inventory && <fieldset><legend>{t.inventory}</legend>
        <button onClick={() => setChoices(inventory.devices.filter(source => source.entities.length).map(source => ({ key: source.key, entityKeys: source.entities.map(entity => entity.key), allowControl: false, overrideRoom: false, roomId: null })))}>{t.selectAll}</button>
        <button onClick={() => setChoices([])}>{t.selectNone}</button>
        {inventory.devices.map(source => {
          const choice = choices.find(choice => choice.key === source.key);
          const powerCount = source.entities.filter(entity => choice?.entityKeys.includes(entity.key) && entity.supportsPower).length;
          return <fieldset key={source.key}><legend><label><input type="checkbox" checked={!!choice} disabled={!source.entities.length} onChange={event => event.target.checked ? update({ key: source.key, entityKeys: source.entities.map(entity => entity.key), allowControl: false, overrideRoom: false, roomId: null }) : setChoices(choices.filter(item => item.key !== source.key))} />{source.name}</label></legend>
            {choice && <>
              <fieldset><legend>{t.entity}</legend>{source.entities.map(entity => <label key={entity.key}><input type="checkbox" checked={choice.entityKeys.includes(entity.key)} onChange={event => {
                const keys = event.target.checked ? [...choice.entityKeys, entity.key] : choice.entityKeys.filter(key => key !== entity.key);
                if (!keys.length) setChoices(choices.filter(item => item.key !== source.key)); else update(changeHaEntities(choice, source, keys));
              }} />{entity.name} ({entity.state})</label>)}</fieldset>
              <label>{t.room}<select value={choice.overrideRoom ? choice.roomId ?? "none" : "auto"} onChange={event => update({ ...choice, overrideRoom: event.target.value !== "auto", roomId: ["auto", "none"].includes(event.target.value) ? null : event.target.value })}>
                <option value="auto">{t.automatic}{source.sourceRoom ? ` (${source.sourceRoom})` : ""}</option><option value="none">{t.unassigned}</option>{rooms.map(room => <option key={room.id} value={room.id}>{room.name}</option>)}
              </select></label>
              <label><input type="checkbox" checked={choice.allowControl} disabled={powerCount !== 1} onChange={event => update({ ...choice, allowControl: event.target.checked })} />{t.control}</label><p>{t.controlSingle}</p>
            </>}
          </fieldset>;
        })}<button onClick={() => setConfirm("apply")}>{t.apply}</button>
      </fieldset>}
    </fieldset>
    {status?.lastSuccessAt && <p>{t.lastSuccess}: {new Date(status.lastSuccessAt).toLocaleString(locale)}</p>}
    {success && <Link href="/devices">{t.openDevices}</Link>}
    <ConfirmDialog open={confirm !== null} onOpenChange={open => { if (!open) setConfirm(null); }} title={confirm === "apply" ? t.applyTitle : t.disconnectTitle} description={confirm === "apply" ? t.applyDescription : t.disconnectDescription} confirmLabel={confirm === "apply" ? t.apply : t.disconnect} cancelLabel={t.cancel} pending={pending} error={error ?? undefined} onConfirm={() => void (confirm === "apply" ? apply() : disconnect())} />
  </section>;
}

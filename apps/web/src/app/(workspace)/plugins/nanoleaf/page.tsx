"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { csrfHeader } from "@/features/auth/csrf";
import { DiscoveredNanoleaf, IntegrationConnection, isConnection, isConnectionList, isDiscoveredNanoleafList, isNanoleafScenes, isNanoleafState, NanoleafScenes, NanoleafState } from "@/features/integrations/contracts";

export default function NanoleafPage() {
  const { t } = useWorkspace();
  const [connections, setConnections] = useState<IntegrationConnection[]>([]);
  const [states, setStates] = useState<Record<string, NanoleafState | null>>({});
  const [pending, setPending] = useState(false);
  const [removeConfirmation, setRemoveConfirmation] = useState<string | null>(null);
  const [discovered, setDiscovered] = useState<DiscoveredNanoleaf[] | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [selectedHost, setSelectedHost] = useState("");
  const [editingNames, setEditingNames] = useState<Record<string, string>>({});
  const [brightnessValues, setBrightnessValues] = useState<Record<string, number>>({});
  const [scenes, setScenes] = useState<Record<string, NanoleafScenes>>({});
  const selectedDevice = discovered?.find((device) => device.host === selectedHost);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    const response = await fetch("/api/integrations/nanoleaf/connections", { cache: "no-store" });
    const value: unknown = await response.json();
    if (!response.ok || !isConnectionList(value)) throw new Error();
    setConnections(value);
  }, []);
  useEffect(() => {
    let disposed = false;
    async function initialLoad() {
      try {
        const response = await fetch("/api/integrations/nanoleaf/connections", { cache: "no-store" });
        const value: unknown = await response.json();
        if (!response.ok || !isConnectionList(value)) throw new Error();
        if (!disposed) setConnections(value);
      } catch { if (!disposed) setError(t.nanoleafError); }
    }
    void initialLoad();
    return () => { disposed = true; };
  }, [t.nanoleafError]);

  async function pair(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError(null); const form = event.currentTarget;
    const data = new FormData(form);
    const response = await fetch("/api/integrations/nanoleaf/connections", { method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify({ host: data.get("host"), displayName: data.get("displayName") }) });
    const value: unknown = await response.json().catch(() => ({}));
    if (response.ok && isConnection(value)) { form.reset(); setSelectedHost(""); await load(); }
    else setError((value as { code?: string }).code === "NANOLEAF_PAIRING_WINDOW_CLOSED" ? t.nanoleafPairingClosed : t.nanoleafError);
    setPending(false);
  }
  async function discover() {
    setDiscovering(true); setError(null);
    const response = await fetch("/api/integrations/nanoleaf/discover", { cache: "no-store" });
    const value: unknown = await response.json().catch(() => null);
    if (response.ok && isDiscoveredNanoleafList(value)) setDiscovered(value); else setError(t.nanoleafError);
    setDiscovering(false);
  }
  async function refresh(id: string) {
    const response = await fetch(`/api/integrations/nanoleaf/connections/${id}/state`, { cache: "no-store" });
    const value: unknown = await response.json().catch(() => null);
    setStates((current) => ({ ...current, [id]: response.ok && isNanoleafState(value) ? value : null }));
  }
  async function power(id: string, on: boolean) {
    setPending(true); const response = await fetch(`/api/integrations/nanoleaf/connections/${id}/power`, { method: "PUT", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify({ on, confirmed: true }) });
    const value: unknown = await response.json().catch(() => null);
    if (response.ok && isNanoleafState(value)) setStates((current) => ({ ...current, [id]: value })); else setError(t.nanoleafError);
    setPending(false);
  }
  async function rename(id: string) {
    const displayName = editingNames[id]?.trim(); if (!displayName) return;
    setPending(true); const response = await fetch(`/api/integrations/nanoleaf/connections/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify({ displayName }) });
    if (response.ok) { await load(); setEditingNames((current) => { const next = { ...current }; delete next[id]; return next; }); } else setError(t.nanoleafError);
    setPending(false);
  }
  async function brightness(id: string) {
    const value = brightnessValues[id] ?? states[id]?.brightness ?? 50; setPending(true);
    const response = await fetch(`/api/integrations/nanoleaf/connections/${id}/brightness`, { method: "PUT", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify({ brightness: value, confirmed: true }) });
    const state: unknown = await response.json().catch(() => null);
    if (response.ok && isNanoleafState(state)) setStates((current) => ({ ...current, [id]: state })); else setError(t.nanoleafError);
    setPending(false);
  }
  async function loadScenes(id: string) {
    setPending(true); const response = await fetch(`/api/integrations/nanoleaf/connections/${id}/scenes`, { cache: "no-store" });
    const value: unknown = await response.json().catch(() => null);
    if (response.ok && isNanoleafScenes(value)) setScenes((current) => ({ ...current, [id]: value })); else setError(t.nanoleafError);
    setPending(false);
  }
  async function selectScene(id: string, name: string) {
    setPending(true); const response = await fetch(`/api/integrations/nanoleaf/connections/${id}/scenes/select`, { method: "PUT", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify({ name, confirmed: true }) });
    const value: unknown = await response.json().catch(() => null);
    if (response.ok && isNanoleafScenes(value)) setScenes((current) => ({ ...current, [id]: value })); else setError(t.nanoleafError);
    setPending(false);
  }
  async function remove(id: string) {
    setPending(true); const response = await fetch(`/api/integrations/nanoleaf/connections/${id}`, { method: "DELETE", headers: csrfHeader() });
    if (response.ok) { setRemoveConfirmation(null); await load(); } else setError(t.nanoleafError); setPending(false);
  }
  return <section className="plugins-stage nanoleaf-stage">
    <Link className="back-link" href="/plugins">← {t.nanoleafBack}</Link>
    <header className="plugins-header"><div><p className="eyebrow">{t.pluginOfficial}</p><h1>{t.nanoleafTitle}</h1><p>{t.nanoleafDescription}</p></div></header>
    <div className="privacy-note">{t.nanoleafPrivacy}</div>
    <article className="pairing-card"><h2>{t.nanoleafHowTitle}</h2><p>{t.nanoleafHow}</p>
      <button className="discover-button" type="button" disabled={discovering} onClick={() => void discover()}>{discovering ? t.nanoleafDiscovering : t.nanoleafDiscover}</button>
      {discovered && <div className="discovered-devices"><strong>{t.nanoleafDiscovered}</strong>{discovered.length === 0 ? <p>{t.nanoleafNoneFound}</p> : discovered.map((device) => <button className={selectedHost === device.host ? "selected" : ""} type="button" aria-pressed={selectedHost === device.host} key={device.host} onClick={() => setSelectedHost(device.host)}><span>{device.name}</span><code>{device.host}</code><small>{selectedHost === device.host ? `✓ ${t.nanoleafSelected}` : t.nanoleafSelect}</small></button>)}</div>}
      {selectedDevice && <p className="selected-device" role="status">{t.nanoleafSelectedDevice.replace("{name}", selectedDevice.name).replace("{host}", selectedDevice.host)}</p>}
      <details className="manual-address" open={discovered?.length === 0}><summary>{t.nanoleafManual}</summary><label>{t.nanoleafHost}<input name="manual-host-preview" inputMode="decimal" placeholder="192.168.1.42" maxLength={45} value={selectedHost} onChange={(event) => setSelectedHost(event.target.value)} /></label></details>
      <form onSubmit={pair}><input name="host" type="hidden" value={selectedHost} /><label>{t.nanoleafName}<input name="displayName" maxLength={160} defaultValue={selectedDevice?.name ?? ""} key={selectedDevice?.host ?? "manual"} /></label><button disabled={pending || !selectedHost}>{selectedDevice ? t.nanoleafConnectSelected : t.nanoleafConnect}</button></form>
      {error && <p className="auth-error" role="alert">{error}</p>}
    </article>
    <h2>{t.nanoleafConnections}</h2>
    {connections.length === 0 ? <p className="placeholder-copy">{t.nanoleafEmpty}</p> : <div className="connection-grid">{connections.map((connection) => <article className={`connection-card ${states[connection.id]?.on ? "is-on" : ""}`} key={connection.id}>
      <div className="connection-heading">{editingNames[connection.id] !== undefined ? <input aria-label={t.nanoleafName} autoFocus value={editingNames[connection.id]} onChange={(event) => setEditingNames((current) => ({ ...current, [connection.id]: event.target.value }))} /> : <div><h3>{connection.displayName}</h3><code>{connection.endpointHost}</code></div>}<button type="button" onClick={() => editingNames[connection.id] !== undefined ? void rename(connection.id) : setEditingNames((current) => ({ ...current, [connection.id]: connection.displayName }))}>{editingNames[connection.id] !== undefined ? t.nanoleafSaveName : t.nanoleafRename}</button></div>
      {states[connection.id] !== undefined && <p>{states[connection.id] ? `${t.nanoleafOnline} · ${states[connection.id]?.brightness ?? "–"}%` : t.nanoleafOffline}</p>}
      <div className="brightness-control"><label><span>{t.nanoleafBrightness}</span><strong>{brightnessValues[connection.id] ?? states[connection.id]?.brightness ?? 50}%</strong><input type="range" min="0" max="100" value={brightnessValues[connection.id] ?? states[connection.id]?.brightness ?? 50} onChange={(event) => setBrightnessValues((current) => ({ ...current, [connection.id]: Number(event.target.value) }))} /></label><button disabled={pending} onClick={() => void brightness(connection.id)}>{t.nanoleafApplyBrightness}</button></div>
      <div className="scene-control"><div><strong>{t.nanoleafScenes}</strong><button disabled={pending} onClick={() => void loadScenes(connection.id)}>{t.nanoleafLoadScenes}</button></div>{scenes[connection.id] && (scenes[connection.id].items.length === 0 ? <p>{t.nanoleafNoScenes}</p> : <div className="scene-list">{scenes[connection.id].items.map((scene) => { const colors=scenes[connection.id].previews[scene]??[]; return <button className={`${scenes[connection.id].active === scene ? "active" : ""} ${colors.length ? "has-preview" : ""}`} style={colors.length ? { backgroundImage: `linear-gradient(135deg, ${colors.join(", ")})` } : undefined} disabled={pending} key={scene} onClick={() => void selectScene(connection.id, scene)}><span>{scene}</span>{scenes[connection.id].active === scene && <small>✓ {t.nanoleafActiveScene}</small>}</button>;})}</div>)}</div>
      <div className="connection-actions"><button disabled={pending} onClick={() => void refresh(connection.id)}>{t.nanoleafRefresh}</button><button disabled={pending} onClick={() => void power(connection.id, true)}>{t.nanoleafTurnOn}</button><button disabled={pending} onClick={() => void power(connection.id, false)}>{t.nanoleafTurnOff}</button><button className="danger" disabled={pending} onClick={() => setRemoveConfirmation(connection.id)}>{t.nanoleafRemove}</button></div>
    </article>)}</div>}
    <ConfirmDialog open={removeConfirmation !== null} onOpenChange={(open) => { if (!open) setRemoveConfirmation(null); }} title={t.nanoleafRemoveTitle} description={t.nanoleafRemoveDescription.replace("{name}", connections.find((item) => item.id === removeConfirmation)?.displayName ?? "Nanoleaf")} confirmLabel={t.nanoleafRemoveConfirm} cancelLabel={t.cancel} pending={pending} onConfirm={() => { if (removeConfirmation) void remove(removeConfirmation); }} />
  </section>;
}

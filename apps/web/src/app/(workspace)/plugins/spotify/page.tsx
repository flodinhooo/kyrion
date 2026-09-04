"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Dialog } from "radix-ui";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import { isSpotifyDeviceList, isSpotifyStatus, type SpotifyDevice, type SpotifyStatus } from "@/features/spotify/contracts";

export default function SpotifyPage() {
  const { t } = useWorkspace();
  const [status, setStatus] = useState<SpotifyStatus | null>(null);
  const [devices, setDevices] = useState<SpotifyDevice[]>([]);
  const [loginOpen, setLoginOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch("/api/integrations/spotify", { cache: "no-store" }); const value: unknown = await response.json();
    if (!response.ok || !isSpotifyStatus(value)) throw new Error(); setStatus(value);
    if (value.connected) { const deviceResponse = await fetch("/api/integrations/spotify/devices", { cache: "no-store" }); const deviceValue: unknown = await deviceResponse.json(); if (deviceResponse.ok && isSpotifyDeviceList(deviceValue)) setDevices(deviceValue); }
  }, []);
  useEffect(() => {
    let disposed = false;
    async function initialLoad() {
      try { await load(); } catch { if (!disposed) setError(true); }
    }
    void initialLoad();
    return () => { disposed = true; };
  }, [load]);

  async function connect() {
    setPending(true); setError(false);
    const response = await fetch("/api/integrations/spotify/authorization", { method: "POST", headers: csrfHeader() });
    const value: unknown = await response.json().catch(() => null);
    if (response.ok && value && typeof value === "object" && typeof (value as { authorizationUrl?: unknown }).authorizationUrl === "string") window.location.assign((value as { authorizationUrl: string }).authorizationUrl);
    else { setError(true); setPending(false); }
  }
  async function transfer(deviceId: string) {
    setPending(true); setError(false); const response = await fetch("/api/integrations/spotify/playback/device", { method: "PUT", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify({ deviceId, play: true }) });
    if (!response.ok) setError(true); else await load(); setPending(false);
  }
  async function disconnect() {
    setPending(true); const response = await fetch("/api/integrations/spotify", { method: "DELETE", headers: csrfHeader() });
    if (response.ok) { setDevices([]); await load(); } else setError(true); setPending(false);
  }

  return <section className="plugins-stage spotify-stage">
    <Link className="back-link" href="/plugins">← {t.spotifyBack}</Link>
    <header className="plugins-header"><div><p className="eyebrow">{t.pluginOfficial}</p><h1>Spotify</h1><p>{t.spotifyDescription}</p></div></header>
    <div className="privacy-note">{t.spotifyPrivacy}</div>
    {!status ? <p>{t.spotifyLoading}</p> : !status.connected ? <article className="pairing-card"><h2>{t.spotifyConnectTitle}</h2><p>{status.configured ? t.spotifyConnectDescription : t.spotifyNotConfigured}</p><button disabled={!status.configured} onClick={() => setLoginOpen(true)}>{t.spotifyConnect}</button></article> : <>
      <article className="pairing-card"><h2>{t.spotifyConnected}</h2><p>{status.accountName}</p><button className="danger" disabled={pending} onClick={() => void disconnect()}>{t.spotifyDisconnect}</button></article>
      <h2>{t.spotifyDevices}</h2><div className="connection-grid">{devices.map((device) => <article className={`connection-card ${device.active ? "is-on" : ""}`} key={device.id}><div className="connection-heading"><div><h3>{device.name}</h3><p>{device.type} · {device.volumePercent ?? "–"}%</p></div><span className={`device-status ${device.active ? "online" : "unknown"}`}>{device.active ? t.spotifyActive : t.spotifyAvailable}</span></div><button disabled={pending || device.restricted} onClick={() => void transfer(device.id)}>{t.spotifyPlayHere}</button></article>)}</div>
      {devices.length === 0 && <p className="placeholder-copy">{t.spotifyNoDevices}</p>}
    </>}
    {error && <p className="auth-error" role="alert">{t.spotifyError}</p>}
    <Dialog.Root open={loginOpen} onOpenChange={setLoginOpen}><Dialog.Portal><Dialog.Overlay className="confirm-dialog-overlay" /><Dialog.Content className="confirm-dialog spotify-login"><Dialog.Title>{t.spotifyLoginTitle}</Dialog.Title><Dialog.Description>{t.spotifyLoginDescription}</Dialog.Description><div className="confirm-dialog-actions"><Dialog.Close asChild><button>{t.cancel}</button></Dialog.Close><button disabled={pending} onClick={() => void connect()}>{t.spotifyContinue}</button></div></Dialog.Content></Dialog.Portal></Dialog.Root>
  </section>;
}

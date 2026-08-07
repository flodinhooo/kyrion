"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import { isGatewayNodeList, type GatewayNode } from "@/features/gateways/contracts";
import { isDiscoveredNanoleafList, type DiscoveredNanoleaf } from "@/features/integrations/contracts";

export default function AddDevicePage() {
  const { t } = useWorkspace();
  const [nodes, setNodes] = useState<GatewayNode[]>([]);
  const [zigbeeCandidates, setZigbeeCandidates] = useState<NonNullable<NonNullable<GatewayNode["health"]>["zigbee"]>["devices"]>([]);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [networkDevices, setNetworkDevices] = useState<DiscoveredNanoleaf[] | null>(null);
  const [networkSearching, setNetworkSearching] = useState(false);
  const [deviceNames, setDeviceNames] = useState<Record<string, string>>({});
  const [addingDevice, setAddingDevice] = useState<string | null>(null);
  const [addedDevices, setAddedDevices] = useState<string[]>([]);
  const [error, setError] = useState(false);

  const loadGateways = useCallback(async () => {
    const response = await fetch("/api/gateways", { cache: "no-store" });
    const value: unknown = await response.json();
    if (!response.ok || !isGatewayNodeList(value)) throw new Error("invalid gateways");
    setNodes(value);
  }, []);

  useEffect(() => {
    let disposed = false;
    const refresh = () => void loadGateways().catch(() => { if (!disposed) setError(true); });
    const timeout = window.setTimeout(refresh, 0);
    const interval = window.setInterval(refresh, 1_000);
    return () => { disposed = true; window.clearTimeout(timeout); window.clearInterval(interval); };
  }, [loadGateways]);

  useEffect(() => {
    const interval = window.setInterval(() => setSecondsLeft((value) => Math.max(0, value - 1)), 1_000);
    return () => window.clearInterval(interval);
  }, []);

  const zigbeeNode = useMemo(() => nodes.find((node) => node.availability === "online"
    && node.health?.services.some((service) => service.id === "zigbee" && service.status === "ready")), [nodes]);
  useEffect(() => {
    if (!zigbeeNode || secondsLeft <= 0) return;
    let disposed = false;
    const loadCandidates = async () => {
      try {
        const response = await fetch(`/api/gateways/${zigbeeNode.id}/zigbee/devices`, { cache: "no-store" });
        const value: unknown = await response.json();
        if (!response.ok || !Array.isArray(value)) throw new Error("invalid candidates");
        if (!disposed) setZigbeeCandidates(value as typeof zigbeeCandidates);
      } catch { if (!disposed) setError(true); }
    };
    void loadCandidates();
    const interval = window.setInterval(loadCandidates, 1_000);
    return () => { disposed = true; window.clearInterval(interval); };
  }, [secondsLeft, zigbeeNode]);

  async function startZigbeeSearch() {
    if (!zigbeeNode) return;
    setError(false);
    setZigbeeCandidates([]);
    const response = await fetch(`/api/gateways/${zigbeeNode.id}/zigbee/pairing`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({ duration: 180 }),
    });
    if (!response.ok) { setError(true); return; }
    setSecondsLeft(180);
  }

  async function searchNetwork() {
    setNetworkSearching(true); setError(false);
    try {
      const response = await fetch("/api/integrations/nanoleaf/discover", { cache: "no-store" });
      const value: unknown = await response.json();
      if (!response.ok || !isDiscoveredNanoleafList(value)) throw new Error("invalid discovery");
      setNetworkDevices(value);
    } catch { setError(true); } finally { setNetworkSearching(false); }
  }

  async function addZigbeeDevice(deviceId: string, fallbackName: string) {
    if (!zigbeeNode) return;
    const displayName = (deviceNames[deviceId] ?? fallbackName).trim();
    if (!displayName) return;
    setAddingDevice(deviceId); setError(false);
    try {
      const response = await fetch(`/api/gateways/${zigbeeNode.id}/zigbee/devices`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({ deviceId, displayName }),
      });
      if (!response.ok) throw new Error("add failed");
      setAddedDevices((current) => [...new Set([...current, deviceId])]);
    } catch { setError(true); } finally { setAddingDevice(null); }
  }

  return <section className="plugins-stage add-device-stage">
    <Link className="back-link" href="/home">← {t.addDeviceBackHome}</Link>
    <header className="plugins-header"><div><p className="eyebrow">Kyrion Discovery</p><h1>{t.addDeviceTitle}</h1><p>{t.addDeviceDescription}</p></div></header>
    {error && <p className="auth-error" role="alert">{t.addDeviceError}</p>}
    <h2>{t.addDeviceAvailableConnections}</h2>
    <div className="discovery-methods">
      <article className="pairing-card">
        <div className="discovery-heading"><div><small>Zigbee · 2.4 GHz</small><h2>{t.addDeviceZigbeeTitle}</h2></div><span className={`device-status ${zigbeeNode ? "online" : "unknown"}`}>{zigbeeNode ? t.addDeviceReady : t.addDeviceUnavailable}</span></div>
        <p>{t.addDeviceZigbeeDescription}</p>
        <button disabled={!zigbeeNode || secondsLeft > 0} onClick={() => void startZigbeeSearch()}>{secondsLeft > 0 ? t.addDeviceSearching.replace("{seconds}", String(secondsLeft)) : t.addDeviceSearch}</button>
        {secondsLeft > 0 && <p className="discovery-hint">{t.addDeviceZigbeeHint}</p>}
        {secondsLeft > 0 && <div className="discovery-results"><strong>{t.addDeviceFound}</strong>{zigbeeCandidates.length === 0 ? <p>{t.addDeviceNoneFound}</p> : zigbeeCandidates.map((device) => {
          const fallbackName = `${device.vendor} ${device.model}`.trim();
          return <div className="discovery-candidate" key={device.ieeeAddress}><div><span>{fallbackName}</span><code>{device.ieeeAddress}</code></div>{addedDevices.includes(device.ieeeAddress) ? <p className="device-status online">{t.addDeviceAdded}</p> : <><label>{t.addDeviceName}<input maxLength={160} value={deviceNames[device.ieeeAddress] ?? fallbackName} onChange={(event) => setDeviceNames((current) => ({ ...current, [device.ieeeAddress]: event.target.value }))} /></label><button disabled={addingDevice === device.ieeeAddress} onClick={() => void addZigbeeDevice(device.ieeeAddress, fallbackName)}>{addingDevice === device.ieeeAddress ? t.addDeviceAdding : t.addDeviceConfirm}</button></>}</div>;
        })}</div>}
      </article>
      <article className="pairing-card">
        <div className="discovery-heading"><div><small>mDNS · IPv4</small><h2>{t.addDeviceNetworkTitle}</h2></div><span className="device-status online">{t.addDeviceReady}</span></div>
        <p>{t.addDeviceNetworkDescription}</p>
        <button disabled={networkSearching} onClick={() => void searchNetwork()}>{networkSearching ? `${t.addDeviceSearch} …` : t.addDeviceSearch}</button>
        {networkDevices && <div className="discovery-results"><strong>{t.addDeviceFound}</strong>{networkDevices.length === 0 ? <p>{t.addDeviceNoneFound}</p> : networkDevices.map((device) => <div key={device.host}><span>{device.name}</span><code>{device.host}</code></div>)}</div>}
        {networkDevices && networkDevices.length > 0 && <Link className="placeholder-action" href="/plugins/nanoleaf">{t.addDeviceNetworkContinue}</Link>}
      </article>
    </div>
  </section>;
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import {
  isGatewayBluetoothDeviceList, isGatewayNodeList, isGatewayZigbeeDeviceList,
  type GatewayBluetoothDevice, type GatewayNode, type GatewayZigbeeDevice,
} from "@/features/gateways/contracts";
import { isNetworkDeviceList, type NetworkDevice } from "@/features/integrations/network-contracts";
import { isConnection } from "@/features/integrations/contracts";
import { diagnosticsMessages } from "@/features/system-services/messages";

export default function AddDevicePage() {
  const { t, locale } = useWorkspace();
  const d = diagnosticsMessages[locale] ?? diagnosticsMessages.en;
  const [nodes, setNodes] = useState<GatewayNode[]>([]);
  const [zigbeeCandidates, setZigbeeCandidates] = useState<GatewayZigbeeDevice[]>([]);
  const [bluetoothCandidates, setBluetoothCandidates] = useState<GatewayBluetoothDevice[]>([]);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [networkDevices, setNetworkDevices] = useState<NetworkDevice[] | null>(null);
  const [shellyError, setShellyError] = useState<string | null>(null);
  const [selectedNetworkHost, setSelectedNetworkHost] = useState<string | null>(null);
  const [networkSearching, setNetworkSearching] = useState(false);
  const [deviceNames, setDeviceNames] = useState<Record<string, string>>({});
  const [deviceClasses, setDeviceClasses] = useState<Record<string, "light" | "switch" | "sensor" | "other">>({});
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
        if (!response.ok || !isGatewayZigbeeDeviceList(value)) throw new Error("invalid candidates");
        if (!disposed) setZigbeeCandidates(value);
      } catch { if (!disposed) setError(true); }
    };
    void loadCandidates();
    const interval = window.setInterval(loadCandidates, 1_000);
    return () => { disposed = true; window.clearInterval(interval); };
  }, [secondsLeft, zigbeeNode]);

  const bluetoothNode = useMemo(() => nodes.find((node) =>
    node.availability === "online" && node.health?.bluetooth), [nodes]);
  useEffect(() => {
    if (!bluetoothNode) return;
    let disposed = false;
    const loadCandidates = async () => {
      try {
        const response = await fetch(
          `/api/gateways/${bluetoothNode.id}/bluetooth/devices`, { cache: "no-store" },
        );
        const value: unknown = await response.json();
        if (!response.ok || !isGatewayBluetoothDeviceList(value)) throw new Error("invalid candidates");
        if (!disposed) setBluetoothCandidates(value);
      } catch { if (!disposed) setError(true); }
    };
    void loadCandidates();
    const interval = window.setInterval(loadCandidates, 3_000);
    return () => { disposed = true; window.clearInterval(interval); };
  }, [bluetoothNode]);

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
    setNetworkDevices(null); setShellyError(null); setSelectedNetworkHost(null);
    try {
      const response = await fetch("/api/integrations/network/discover", { method: "POST", headers: csrfHeader(), cache: "no-store" });
      const value: unknown = await response.json();
      if (!response.ok || !isNetworkDeviceList(value)) throw new Error("invalid discovery");
      setNetworkDevices(value);
    } catch { setError(true); } finally { setNetworkSearching(false); }
  }

  async function addShelly(host: string, fallbackName: string) {
    setAddingDevice(host); setShellyError(null);
    try {
      const response = await fetch("/api/integrations/shelly/connections", {
        method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({ host, displayName: deviceNames[host] ?? fallbackName, confirmed: true }),
      });
      const value: unknown = await response.json();
      if (!response.ok || !isConnection(value)) {
        const code = value && typeof value === "object" && "code" in value ? value.code : null;
        setShellyError(code === "SHELLY_AUTH_REQUIRED" ? t.shellyAuthRequired
          : code === "SHELLY_UNSUPPORTED_DEVICE" ? t.shellyUnsupported : t.shellyUnavailable);
        return;
      }
      setAddedDevices((current) => [...new Set([...current, host])]);
    } catch { setShellyError(t.shellyUnavailable); } finally { setAddingDevice(null); }
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
        body: JSON.stringify({ deviceId, displayName, deviceClass: deviceClasses[deviceId] ?? "other" }),
      });
      if (!response.ok) throw new Error("add failed");
      setAddedDevices((current) => [...new Set([...current, deviceId])]);
    } catch { setError(true); } finally { setAddingDevice(null); }
  }

  async function addBluetoothDevice(deviceId: string, fallbackName: string) {
    if (!bluetoothNode) return;
    const displayName = (deviceNames[deviceId] ?? fallbackName).trim();
    if (!displayName) return;
    setAddingDevice(deviceId); setError(false);
    try {
      const response = await fetch(`/api/gateways/${bluetoothNode.id}/bluetooth/devices`, {
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
    <header className="plugins-header"><div><h1>{t.addDeviceTitle}</h1><p>{t.addDeviceDescription}</p></div></header>
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
          return <div className="discovery-candidate" key={device.ieeeAddress}><div><span>{fallbackName}</span><code>{device.ieeeAddress}</code></div>{addedDevices.includes(device.ieeeAddress) ? <p className="device-status online">{t.addDeviceAdded}</p> : <><label>{t.addDeviceName}<input maxLength={160} value={deviceNames[device.ieeeAddress] ?? fallbackName} onChange={(event) => setDeviceNames((current) => ({ ...current, [device.ieeeAddress]: event.target.value }))} /></label><label>{t.deviceClass}<select value={deviceClasses[device.ieeeAddress] ?? "other"} onChange={(event) => setDeviceClasses((current) => ({ ...current, [device.ieeeAddress]: event.target.value as "light" | "switch" | "sensor" | "other" }))}>{(["light", "switch", "sensor", "other"] as const).map((value) => <option key={value} value={value}>{t.deviceClasses[value]}</option>)}</select></label><button disabled={addingDevice === device.ieeeAddress} onClick={() => void addZigbeeDevice(device.ieeeAddress, fallbackName)}>{addingDevice === device.ieeeAddress ? t.addDeviceAdding : t.addDeviceConfirm}</button></>}</div>;
        })}</div>}
      </article>
      <article className="pairing-card">
        <div className="discovery-heading"><div><small>Bluetooth LE · 2.4 GHz</small><h2>{t.addDeviceBluetoothTitle}</h2></div><span className={`device-status ${bluetoothNode ? "online" : "unknown"}`}>{bluetoothNode ? t.addDeviceReady : t.addDeviceUnavailable}</span></div>
        <p>{t.addDeviceBluetoothDescription}</p>
        <p className="discovery-hint">{t.addDeviceBluetoothHint}</p>
        <div className="discovery-results"><strong>{t.addDeviceFound}</strong>
          {bluetoothCandidates.length === 0 ? <p>{t.addDeviceNoneFound}</p> : bluetoothCandidates.map((device) => {
            const fallbackName = `${device.name} ${device.model}`;
            return <div className="discovery-candidate" key={device.address}><div><span>{fallbackName}</span><code>{device.address}</code></div>
              {addedDevices.includes(device.address) ? <p className="device-status online">{t.addDeviceAdded}</p> : <>
                <label>{t.addDeviceName}<input maxLength={160} value={deviceNames[device.address] ?? fallbackName} onChange={(event) => setDeviceNames((current) => ({ ...current, [device.address]: event.target.value }))} /></label>
                <button disabled={addingDevice === device.address} onClick={() => void addBluetoothDevice(device.address, fallbackName)}>{addingDevice === device.address ? t.addDeviceAdding : t.addDeviceConfirm}</button>
              </>}
            </div>;
          })}
        </div>
      </article>
      <article className="pairing-card">
        <div className="discovery-heading"><div><small>mDNS · IPv4</small><h2>{t.addDeviceNetworkTitle}</h2></div><span className="device-status online">{t.addDeviceReady}</span></div>
        <button disabled={networkSearching} onClick={() => void searchNetwork()}>{networkSearching ? `${t.addDeviceSearch} …` : t.addDeviceSearch}</button>
        <p>{d.shellyPath}</p><Link className="placeholder-action" href="/settings/services">{d.haOpen}</Link>
        {networkDevices && <div className="discovery-results"><strong>{t.addDeviceFound} · {networkDevices.length}</strong>{networkDevices.length === 0 ? <p>{t.addDeviceNoneFound}</p> : networkDevices.map((device) => <details className="discovery-candidate network-candidate" key={device.host} onToggle={(event) => { if (event.currentTarget.open) { setSelectedNetworkHost(device.host); setShellyError(null); } }}>
          <summary><span>{device.name}{(device.connected || addedDevices.includes(device.host)) && <small className="network-connected">{t.networkDeviceConnected}</small>}</span><code>{device.host}</code></summary>
          {(device.connected || addedDevices.includes(device.host)) ? <Link className="placeholder-action" href="/devices">{t.shellyViewDevices}</Link>
            : device.provider === "nanoleaf" ? <Link className="placeholder-action" href="/plugins/nanoleaf">{t.addDeviceNetworkContinue}</Link>
            : device.provider === "network" ? <p>{t.networkDeviceUnsupported}</p>
            : addedDevices.includes(device.host) ? <p role="status">{t.addDeviceAdded}</p> : <>
              <p>{t.shellyWakeHint}</p>
              <label>{t.addDeviceName}<input maxLength={160} value={deviceNames[device.host] ?? device.name} onChange={(event) => setDeviceNames((current) => ({ ...current, [device.host]: event.target.value }))} /></label>
              <button disabled={addingDevice !== null} onClick={() => void addShelly(device.host, device.name)}>{addingDevice === device.host ? t.addDeviceAdding : t.shellyConnect}</button>
              {shellyError && selectedNetworkHost === device.host && <p className="auth-error" role="alert">{shellyError}</p>}
            </>}
        </details>)}</div>}
        {addedDevices.length > 0 && <Link className="placeholder-action" href="/devices">{t.shellyViewDevices}</Link>}
      </article>
    </div>
  </section>;
}

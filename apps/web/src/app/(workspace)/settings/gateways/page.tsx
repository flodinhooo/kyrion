"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";
import { csrfHeader } from "@/features/auth/csrf";
import {
  isGatewayEnrollment, isGatewayNodeList, type GatewayEnrollment, type GatewayNode,
} from "@/features/gateways/contracts";

const serviceKeys = ["home-assistant", "matter", "mqtt", "otbr", "voice", "zigbee"] as const;
const serviceLabelKeys = {
  "home-assistant": "gatewayService_home_assistant",
  matter: "gatewayService_matter",
  mqtt: "gatewayService_mqtt",
  otbr: "gatewayService_otbr",
  voice: "gatewayService_voice",
  zigbee: "gatewayService_zigbee",
} as const;
const serviceStatusKeys = {
  ready: "gatewayServiceStatus_ready",
  unavailable: "gatewayServiceStatus_unavailable",
  not_configured: "gatewayServiceStatus_not_configured",
  degraded: "gatewayServiceStatus_degraded",
  unknown: "gatewayServiceStatus_unknown",
} as const;

export default function GatewaysPage() {
  const { locale, t } = useWorkspace();
  const [nodes, setNodes] = useState<GatewayNode[]>([]);
  const [enrollment, setEnrollment] = useState<GatewayEnrollment | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch("/api/gateways", { cache: "no-store" });
    const value: unknown = await response.json();
    if (!response.ok || !isGatewayNodeList(value)) throw new Error("Invalid gateways");
    setNodes(value); setError(false); setLoading(false);
  }, []);

  useEffect(() => {
    let disposed = false;
    const refresh = () => void load().catch(() => { if (!disposed) { setError(true); setLoading(false); } });
    const timeout = window.setTimeout(refresh, 0);
    const interval = window.setInterval(refresh, 15_000);
    return () => { disposed = true; window.clearTimeout(timeout); window.clearInterval(interval); };
  }, [load]);

  async function createEnrollment() {
    setPending(true); setError(false);
    try {
      const response = await fetch("/api/gateways/enrollments", {
        method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({ displayName: "kyrion-node" }),
      });
      const value: unknown = await response.json();
      if (!response.ok || !isGatewayEnrollment(value)) throw new Error("Invalid enrollment");
      setEnrollment(value);
    } catch { setError(true); } finally { setPending(false); }
  }

  const formatBytes = (value: number) => new Intl.NumberFormat(locale, {
    style: "unit", unit: "gigabyte", maximumFractionDigits: 1,
  }).format(value / 1_073_741_824);
  const formatTime = (value: string) => new Intl.DateTimeFormat(locale, {
    dateStyle: "short", timeStyle: "medium",
  }).format(new Date(value));

  return <section className="gateway-stage">
    <header className="gateway-header">
      <div><p className="eyebrow">Kyrion Gateway</p><h1>{t.gatewayTitle}</h1><p>{t.gatewayDescription}</p></div>
      <button disabled={pending} onClick={() => void createEnrollment()}><Icons.plus />{pending ? t.gatewayCreating : t.gatewayCreateEnrollment}</button>
    </header>
    {error && <p className="auth-error">{t.gatewayError}</p>}
    {enrollment && <section className="gateway-enrollment">
      <div><strong>{t.gatewayEnrollmentReady}</strong><small>{t.gatewayEnrollmentExpires}: {formatTime(enrollment.expiresAt)}</small></div>
      <code>{enrollment.enrollmentToken}</code>
      <p>{t.gatewayEnrollmentPrivacy}</p>
    </section>}
    {loading ? <p className="gateway-empty">{t.gatewayLoading}</p>
      : nodes.length === 0 ? <p className="gateway-empty">{t.gatewayEmpty}</p>
        : <div className="gateway-list">{nodes.map((node) => <article className="gateway-card" key={node.id}>
          <div className="gateway-card-heading">
            <div><span className={`device-status ${node.availability}`}>{t[`gatewayStatus_${node.availability}`]}</span><h2>{node.displayName}</h2><small>{node.hostname}</small></div>
            <div className="gateway-version">{node.osName} · {node.architecture}<small>{t.gatewayAgent} {node.agentVersion}</small></div>
          </div>
          {node.lastSeenAt && <p className="gateway-observed">{t.gatewayLastSeen}: {formatTime(node.lastSeenAt)}</p>}
          {node.health && <>
            <div className="gateway-metrics">
              <Metric label={t.gatewayTemperature} value={node.health.temperatureCelsius === null ? "–" : `${node.health.temperatureCelsius.toFixed(1)} °C`} />
              <Metric label={t.gatewayThrottling} value={node.health.throttled ? t.gatewayThrottled : t.gatewayNotThrottled} />
              <Metric label={t.gatewayMemory} value={`${formatBytes(node.health.memoryTotalBytes - node.health.memoryAvailableBytes)} / ${formatBytes(node.health.memoryTotalBytes)}`} />
              <Metric label={t.gatewayStorage} value={`${formatBytes(node.health.storageTotalBytes - node.health.storageAvailableBytes)} / ${formatBytes(node.health.storageTotalBytes)}`} />
              <Metric label={t.gatewayEthernet} value={node.health.ethernet.connected ? t.gatewayConnected : t.gatewayDisconnected} />
              <Metric label={t.gatewayWifi} value={node.health.wifi.connected ? t.gatewayConnected : t.gatewayDisconnected} />
              <Metric label="IPv6" value={node.health.ipv6 ? t.gatewayReady : t.gatewayUnavailable} />
              <Metric label="Bluetooth" value={node.health.bluetooth ? t.gatewayReady : t.gatewayUnavailable} />
            </div>
            <h3>{t.gatewayAdapters}</h3>
            {node.health.adapters.length === 0
              ? <p className="gateway-observed">{t.gatewayAdaptersEmpty}</p>
              : <div className="gateway-services">{node.health.adapters.map((adapter) => <div key={adapter.id}>
                <strong>{adapter.model}</strong>
                <span className="device-status online">{adapter.protocol === "zigbee" ? t.gatewayAdapterZigbee : t.gatewayAdapterThread} · {t.gatewayDetected}</span>
              </div>)}</div>}
            <h3>{t.gatewayServices}</h3>
            <div className="gateway-services">{serviceKeys.map((id) => {
              const service = node.health?.services.find((item) => item.id === id);
              const status = service?.status ?? "unknown";
              return <div key={id}><strong>{t[serviceLabelKeys[id]]}</strong><span className={`device-status ${status === "ready" ? "online" : status === "degraded" ? "degraded" : "unknown"}`}>{t[serviceStatusKeys[status]]}</span></div>;
            })}</div>
          </>}
        </article>)}</div>}
    <Link className="placeholder-action" href="/settings"><Icons.settings />{t.backToSettings}</Link>
  </section>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><small>{label}</small><strong>{value}</strong></div>;
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";
import { isSystemServicesStatus, type SystemService } from "@/features/system-services/contracts";

const gatewayLabels: Record<string, "gatewayService_home_assistant" | "gatewayService_matter" | "gatewayService_mqtt" | "gatewayService_otbr" | "gatewayService_voice" | "gatewayService_zigbee"> = {
  "home-assistant": "gatewayService_home_assistant", matter: "gatewayService_matter", mqtt: "gatewayService_mqtt",
  otbr: "gatewayService_otbr", voice: "gatewayService_voice", zigbee: "gatewayService_zigbee",
};

export default function SystemServicesPage() {
  const { locale, t } = useWorkspace();
  const [services, setServices] = useState<SystemService[]>([]);
  const [observedAt, setObservedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch("/api/system-services", { cache: "no-store" });
    const value: unknown = await response.json().catch(() => null);
    if (!response.ok || !isSystemServicesStatus(value)) throw new Error("invalid service status");
    setServices(value.services); setObservedAt(value.observedAt); setLoading(false); setError(false);
  }, []);

  useEffect(() => {
    let disposed = false;
    const refresh = () => void load().catch(() => { if (!disposed) { setLoading(false); setError(true); } });
    const timeout = window.setTimeout(refresh, 0);
    const interval = window.setInterval(refresh, 5_000);
    return () => { disposed = true; window.clearTimeout(timeout); window.clearInterval(interval); };
  }, [load]);

  const statusLabel = (status: SystemService["status"]) => t[`systemServicesStatus_${status}`];
  const serviceName = (service: SystemService) => {
    const childId = service.id.split(":").at(-1) ?? "";
    return service.source === "gateway" && gatewayLabels[childId] ? t[gatewayLabels[childId]] : service.displayName;
  };

  return <section className="gateway-stage system-services-stage">
    <header className="gateway-header">
      <div><p className="eyebrow">Kyrion Runtime</p><h1>{t.systemServicesTitle}</h1><p>{t.systemServicesDescription}</p></div>
      <button onClick={() => void load()} disabled={loading}><Icons.activity />{t.systemServicesRefresh}</button>
    </header>
    {error && <p className="auth-error">{t.systemServicesError}</p>}
    {loading ? <p className="gateway-empty">{t.systemServicesLoading}</p> : <div className="system-services-grid">
      {services.map((service) => <article className="system-service-card" key={service.id}>
        <div className="system-service-heading"><div><h2>{serviceName(service)}</h2><small>{service.source === "gateway" ? t.systemServicesSourceGateway : t.systemServicesSourceHost}</small></div>
          <span className={`device-status ${service.status === "ready" ? "online" : service.status}`}>{statusLabel(service.status)}</span></div>
        <dl><div><dt>{t.systemServicesHost}</dt><dd>{service.host}</dd></div><div><dt>{t.systemServicesPort}</dt><dd>{service.port ?? "–"}</dd></div>
          <div><dt>{t.systemServicesLatency}</dt><dd>{service.latencyMs === null ? "–" : `${service.latencyMs} ms`}</dd></div></dl>
        {service.detail && <small>{t.systemServicesLastSeen}: {new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "medium" }).format(new Date(service.detail))}</small>}
      </article>)}
    </div>}
    {observedAt && <p className="gateway-observed">{t.systemServicesObservedAt}: {new Intl.DateTimeFormat(locale, { timeStyle: "medium" }).format(new Date(observedAt))}</p>}
    <p className="system-services-note">{t.systemServicesControlNote}</p>
    <Link className="placeholder-action" href="/settings"><Icons.settings />{t.backToSettings}</Link>
  </section>;
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icons } from "@/components/icons";
import { useWorkspace } from "@/components/app-shell";
import { loadIntegrationCatalog, loadingCatalog, type CatalogStatus, type IntegrationDefinition } from "@/features/integrations/catalog";

export default function PluginsPage() {
  const { t } = useWorkspace();
  const [catalog, setCatalog] = useState(loadingCatalog);
  const [revision, setRevision] = useState(0);
  const loading = Object.values(catalog).some((entry) => entry.status === "loading");

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10_000);
    void loadIntegrationCatalog(controller.signal).then((value) => {
      if (!disposed) setCatalog(value);
    }).finally(() => window.clearTimeout(timeout));
    return () => { disposed = true; controller.abort(); window.clearTimeout(timeout); };
  }, [revision]);

  const statusLabels: Record<CatalogStatus, string> = {
    loading: t.catalogLoading, error: t.catalogError, available: t.catalogAvailable,
    configured: t.catalogConfigured, connected: t.pluginConnected,
    server_configuration: t.catalogServerConfiguration,
  };
  const cards: IntegrationDefinition[] = [
    { id: "nanoleaf", name: "Nanoleaf", description: t.pluginNanoleafDescription, kind: "local", authType: "local", capabilities: [{ id: "devices.control", label: t.integrationCapabilityDeviceControl, enabled: true }], href: "/plugins/nanoleaf", live: true },
    { id: "zigbee", name: "Zigbee", description: t.pluginZigbeeDescription, kind: "local", authType: "local", capabilities: [{ id: "devices.discovery", label: t.integrationCapabilityDiscovery, enabled: true }], href: "/settings/gateways", live: true },
    { id: "jellyfin", name: "Jellyfin", description: t.integrationJellyfinDescription, kind: "local", authType: "token", capabilities: [{ id: "media.library", label: t.integrationCapabilityMedia, enabled: false }], href: "/plugins", live: false },
    { id: "spotify", name: "Spotify", description: t.pluginSpotifyDescription, kind: "cloud", authType: "oauth", capabilities: [{ id: "media.playback", label: t.integrationCapabilityPlayback, enabled: true }], href: "/plugins/spotify", live: true },
    { id: "google", name: "Google", description: t.integrationGoogleDescription, kind: "cloud", authType: "oauth", capabilities: [{ id: "calendar.read", label: t.integrationCapabilityCalendar, enabled: false }, { id: "mail.read", label: t.integrationCapabilityMail, enabled: false }], href: "/plugins", live: false },
  ];

  const renderGroup = (kind: "local" | "cloud", title: string) => <section className="integration-group" aria-labelledby={`${kind}-integrations`}>
    <div className="integration-group-heading"><div><p className="eyebrow">{kind === "local" ? t.integrationLocal : t.integrationCloud}</p><h2 id={`${kind}-integrations`}>{title}</h2></div><span className="integration-count">{cards.filter((card) => card.kind === kind).length}</span></div>
    <div className="plugin-grid">{cards.filter((card) => card.kind === kind).map((card) => {
      const entry = catalog[card.id as keyof typeof catalog];
      const ready = card.live && entry && (entry.status === "configured" || entry.status === "connected");
      const status = !card.live ? t.integrationPlanned : entry ? statusLabels[entry.status] : t.integrationPlanned;
      return <article className="plugin-card" key={card.id}>
        <div className="plugin-card-top"><div className="plugin-mark"><Icons.plugins /></div><span className={`integration-kind integration-kind-${card.kind}`}>{card.kind === "local" ? t.integrationLocal : t.integrationCloud}</span></div>
        <h3>{card.name}</h3><p>{card.description}</p>
        <div className={`catalog-status ${!card.live ? "catalog-status-planned" : entry ? `catalog-status-${entry.status}` : ""}`} role="status">{status}</div>
        <div className="integration-capabilities"><span>{t.integrationCapabilities}</span>{card.capabilities.map((capability) => <span className={`capability-pill ${capability.enabled ? "enabled" : ""}`} key={capability.id}>{capability.enabled ? "✓" : "○"} {capability.label}</span>)}</div>
        <Link href={card.href}>{!card.live ? t.integrationViewPlan : ready ? t.catalogManage : t.pluginOpen}</Link>
      </article>;
    })}</div>
  </section>;
  

  return <section className="plugins-stage">
    <header className="plugins-header"><div><h1>{t.pluginsTitle}</h1><p>{t.pluginsDescription}</p></div>
      <button className="catalog-reload" type="button" disabled={loading} onClick={() => { setCatalog(loadingCatalog()); setRevision((value) => value + 1); }}>{loading ? t.catalogLoading : t.catalogRetry}</button>
    </header>
    <div className="integration-groups">{renderGroup("local", t.integrationLocalTitle)}{renderGroup("cloud", t.integrationCloudTitle)}</div>
  </section>;
}

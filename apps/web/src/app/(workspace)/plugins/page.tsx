"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icons } from "@/components/icons";
import { useWorkspace } from "@/components/app-shell";
import { loadIntegrationCatalog, loadingCatalog, type CatalogStatus } from "@/features/integrations/catalog";

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
  const cards = [
    { id: "nanoleaf", name: "Nanoleaf", description: t.pluginNanoleafDescription, href: "/plugins/nanoleaf", setup: t.catalogSetup, detail: t.catalogConnections },
    { id: "zigbee", name: "Zigbee", description: t.pluginZigbeeDescription, href: "/settings/gateways", setup: t.catalogGatewaySetup, detail: t.catalogGateways },
    { id: "spotify", name: "Spotify", description: t.pluginSpotifyDescription, href: "/plugins/spotify", setup: t.catalogSpotifyConnect, detail: null },
  ] as const;

  return <section className="plugins-stage">
    <header className="plugins-header"><div><h1>{t.pluginsTitle}</h1><p>{t.pluginsDescription}</p></div>
      <button className="catalog-reload" type="button" disabled={loading} onClick={() => { setCatalog(loadingCatalog()); setRevision((value) => value + 1); }}>{loading ? t.catalogLoading : t.catalogRetry}</button>
    </header>
    <div className="plugin-grid">{cards.map((card) => {
      const entry = catalog[card.id];
      const ready = entry.status === "configured" || entry.status === "connected";
      return <article className="plugin-card" key={card.id}>
        <div className="plugin-mark"><Icons.plugins /></div>
        <div className="plugin-badges"><span>{t.pluginOfficial}</span></div>
        <h2>{card.name}</h2><p>{card.description}</p>
        <div className={`catalog-status catalog-status-${entry.status}`} role="status">{statusLabels[entry.status]}</div>
        {card.detail && entry.count !== undefined && entry.count > 0 && <small className="catalog-detail">{card.detail.replace("{count}", String(entry.count))}</small>}
        <Link href={card.href}>{ready ? t.catalogManage : entry.status === "available" ? card.setup : t.pluginOpen}</Link>
      </article>;
    })}</div>
  </section>;
}

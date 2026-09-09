"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { isCoreConnectionList, isCoreProviderList, type CoreConnection, type CoreProvider } from "@/features/integrations/catalog-contracts";

const customRoutes: Record<string, string> = { spotify: "/plugins/spotify", nanoleaf: "/plugins/nanoleaf", zigbee: "/settings/gateways" };

export default function IntegrationProviderPage() {
  const { t } = useWorkspace();
  const { providerId } = useParams<{ providerId: string }>();
  const [provider, setProvider] = useState<CoreProvider | null>(null);
  const [connection, setConnection] = useState<CoreConnection | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([fetch("/api/integration-catalog/providers", { cache: "no-store", signal: controller.signal }), fetch("/api/integration-catalog/connections", { cache: "no-store", signal: controller.signal })]).then(async ([providerResponse, connectionResponse]) => {
      const [providers, connections] = await Promise.all([providerResponse.json(), connectionResponse.json()]);
      if (!isCoreProviderList(providers) || !isCoreConnectionList(connections)) throw new Error("Invalid integration catalog");
      setProvider(providers.find((item) => item.id === providerId) ?? null);
      setConnection(connections.find((item) => item.providerId === providerId) ?? null);
      setState("ready");
    }).catch(() => setState("error"));
    return () => controller.abort();
  }, [providerId]);
  if (state === "loading") return <section className="plugins-stage"><p role="status">{t.catalogLoading}</p></section>;
  if (state === "error" || !provider) return <section className="plugins-stage"><p role="status">{t.catalogError}</p><Link href="/plugins">← {t.plugins}</Link></section>;
  const planned = provider.availability === "PLANNED";
  const route = customRoutes[provider.id];
  return <section className="plugins-stage integration-detail">
    <Link className="back-link" href="/plugins">← {t.plugins}</Link>
    <header className="plugins-header"><div><p className="eyebrow">{provider.locality === "LOCAL" ? t.integrationLocal : t.integrationCloud}</p><h1>{provider.name}</h1><p>{provider.description}</p></div></header>
    <div className="integration-detail-grid">
      <article className="connection-card"><p className="eyebrow">{t.integrationStatus}</p><h2>{planned ? t.integrationPlanned : connection?.status ?? t.catalogAvailable}</h2><p>{connection?.displayIdentity ?? t.integrationNoConnection}</p>{connection?.health && <p>{t.integrationHealth}: {connection.health}</p>}</article>
      <article className="connection-card"><p className="eyebrow">{t.integrationAuthentication}</p><h2>{provider.authentication}</h2><p>{provider.locality === "LOCAL" ? t.integrationLocal : t.integrationCloud}</p></article>
    </div>
    <article className="connection-card"><p className="eyebrow">{t.integrationCapabilities}</p>{provider.capabilities.length === 0 ? <p>{planned ? t.integrationPlanned : t.integrationNoCapabilities}</p> : <div className="integration-capabilities">{provider.capabilities.map((capability) => <span className={`capability-pill ${connection?.enabledCapabilities.includes(capability.id) ? "enabled" : ""}`} key={capability.id}>{connection?.enabledCapabilities.includes(capability.id) ? "✓" : "○"} {capability.name}<small> {capability.id}</small></span>)}</div>}</article>
    {route && <Link className="catalog-reload" href={route}>{t.integrationConfigure}</Link>}
  </section>;
}

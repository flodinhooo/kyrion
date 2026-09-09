import { isConnectionList } from "./contracts";
import { isGatewayNodeList } from "../gateways/contracts";
import { isSpotifyStatus } from "../spotify/contracts";

export type CatalogStatus = "loading" | "error" | "available" | "configured" | "connected" | "server_configuration";
export type CatalogEntry = { status: CatalogStatus; count?: number };
export type IntegrationCatalog = { nanoleaf: CatalogEntry; zigbee: CatalogEntry; spotify: CatalogEntry };

export type IntegrationAuthType = "local" | "oauth" | "token" | "none";
export type IntegrationKind = "local" | "cloud";
export type IntegrationCapability = { id: string; label: string; enabled: boolean };
export type IntegrationDefinition = {
  id: keyof IntegrationCatalog | "google" | "jellyfin";
  name: string;
  description: string;
  kind: IntegrationKind;
  authType: IntegrationAuthType;
  capabilities: IntegrationCapability[];
  href: string;
  live: boolean;
};

export function loadingCatalog(): IntegrationCatalog {
  return { nanoleaf: { status: "loading" }, zigbee: { status: "loading" }, spotify: { status: "loading" } };
}

async function readEntry(path: string, parse: (value: unknown) => CatalogEntry, signal: AbortSignal): Promise<CatalogEntry> {
  try {
    const response = await fetch(path, { cache: "no-store", signal });
    if (!response.ok) return { status: "error" };
    return parse(await response.json());
  } catch { return { status: "error" }; }
}

export async function loadIntegrationCatalog(signal: AbortSignal): Promise<IntegrationCatalog> {
  const [nanoleaf, zigbee, spotify] = await Promise.all([
    readEntry("/api/integrations/nanoleaf/connections", (value) => {
      if (!isConnectionList(value)) return { status: "error" };
      return { status: value.length ? "configured" : "available", count: value.length };
    }, signal),
    readEntry("/api/gateways", (value) => {
      if (!isGatewayNodeList(value)) return { status: "error" };
      // Registration does not imply that Zigbee or the gateway is reachable.
      return { status: value.length ? "configured" : "available", count: value.length };
    }, signal),
    readEntry("/api/integrations/spotify", (value) => {
      if (!isSpotifyStatus(value)) return { status: "error" };
      return { status: !value.configured ? "server_configuration" : value.connected ? "connected" : "available" };
    }, signal),
  ]);
  return { nanoleaf, zigbee, spotify };
}

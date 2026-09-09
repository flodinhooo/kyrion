# Integration management

The Web application exposes the central integration catalog at `/plugins`.
It separates local integrations from optional external or cloud integrations.
Core is the source of truth for the provider registry and owner-scoped
connection summaries; the Web application proxies these APIs. Core remains
the authority for connections, permissions, provider calls, persistence and
audit records.

## Current model

An integration definition describes identity, category (local or cloud),
authentication type and provider-neutral capability identifiers. The current
Core API uses `NONE`, `OAUTH`, `API_KEY`, `CREDENTIALS`, `LOCAL_DISCOVERY`,
`DEVICE_FLOW` and `CUSTOM`. A connection contains only safe metadata in browser
responses. Credentials remain Core-owned and encrypted according to ADR 0005.
One provider may have multiple connections and capabilities.

Provider availability (`LIVE`, `IN_DEVELOPMENT`, `PLANNED`) is separate from
connection status (`CONNECTED`, `DISCONNECTED`, `CONFIGURATION_REQUIRED`,
`DEGRADED`, `ERROR`). Supported capabilities belong to the provider. Granted
capabilities belong to a connection through `enabledCapabilities`; the current
read-only catalog reports this boundary without yet persisting editable grants.
Physical resources remain owned by the existing device, room and gateway
models.

Nanoleaf, Zigbee, Spotify and the initial Google Calendar read capability use
live provider routes. Jellyfin remains a catalog placeholder. Google does not
authorize other Google services automatically; each future capability must be
added explicitly with its own provider scope mapping.

## Google OAuth and consumer deployment

Development may provide `KYRION_GOOGLE_CLIENT_ID`,
`KYRION_GOOGLE_CLIENT_SECRET` and `KYRION_GOOGLE_REDIRECT_URI` through Core
environment configuration. These variables are deployment inputs for a
developer or operator and are never part of the end-user setup flow.

For a consumer appliance, Kyrion should provision a product-owned Google OAuth
application. A client secret shipped to every appliance cannot be treated as
confidential, so the production design must not rely on that secret as a trust
anchor. The recommended future design is a minimal Kyrion-operated HTTPS
callback at `auth.kyrion.ch` (or an equivalent product domain). It validates
the provider response and a short-lived, one-time, owner-bound handoff, then
redirects the result to the initiating local installation. Core keeps the
Google tokens encrypted locally and continues making Calendar API requests
directly to Google. The broker must not proxy normal Calendar traffic or hold
long-lived customer tokens.

Direct `kyrion-node.local` callbacks can work only where the hostname is
reachable by the provider's browser flow and the registered HTTPS certificate
and redirect URI are valid. They are suitable for controlled development or a
managed installation, but are not a reliable general consumer callback behind
NAT and private home DNS. Loopback or device authorization should be used only
where Google supports it for the relevant client type.

The customer experience remains one click: **Connect Google**, Google consent,
then **Connected**. Customers must not create Cloud projects, edit `.env`
files, enter client credentials or configure redirect URIs.

## API boundary

Core exposes authenticated `GET /v1/integration-catalog/providers`,
`/providers/{id}`, `/connections` and `/connections/{id}`. The Web proxies these
at `/api/integration-catalog/...`. Responses contain no access tokens, refresh
tokens, API keys, encrypted credential blobs or encryption material.

Existing configuration routes remain active: Nanoleaf uses `/plugins/nanoleaf`,
Zigbee uses `/settings/gateways`, and Spotify uses `/plugins/spotify` with its
existing Core-owned OAuth flow.

## Adding an integration

Add a provider definition and typed capability metadata to the catalog, then
add a Core-owned API and a provider-specific detail view only where generic
configuration is insufficient. Provider authentication must be implemented in
Core or an approved adapter. The Web layer may proxy authenticated requests,
but must never receive access tokens or store secrets in browser storage.

### Adding a new Kyrion integration

1. Register provider metadata and its supported capabilities in Core.
2. Choose an authentication type without assuming OAuth.
3. Implement Core-owned connection and provider configuration logic where
   required, returning sanitized connection metadata.
4. Connect discovered resources or devices to existing Kyrion models.
5. Add the Web proxy/detail escape hatch and German and English translations.
6. Add serialization, ownership, compatibility and secret-sanitization tests.
7. Update this guide and the provider documentation.

## Follow-up

- Persist and manage granular capability grants when a provider requires it;
  use a separate connection-capability relation so supported capabilities stay
  immutable provider metadata.
- Implement OAuth callback and state validation per provider.
- Add encrypted token storage, refresh and revoked-credential handling.
- Add connection health and audit-visible reconnect/disconnect operations.
- Define plugin installation, update, signature, isolation and rollback
  lifecycle before third-party plugins are supported.

# Integration management

The Web application exposes the central integration catalog at `/plugins`.
It separates local integrations from optional external or cloud integrations.
The catalog is a presentation boundary; Core remains the authority for
connections, permissions, provider calls, persistence and audit records.

## Current model

An integration definition describes identity, category (local or cloud),
authentication type (`local`, `oauth`, `token` or `none`) and provider-neutral
capability identifiers. A connection contains only safe metadata in browser
responses. Credentials remain Core-owned and encrypted according to ADR 0005.
One provider connection may expose multiple capabilities; future Google-like
providers should therefore manage capability grants independently.

Nanoleaf, Zigbee and Spotify use existing live routes. Google and Jellyfin are
catalog placeholders and are visibly marked planned. The UI does not invent
provider scopes and does not implement fake OAuth.

## Adding an integration

Add a provider definition and typed capability metadata to the catalog, then
add a Core-owned API and a provider-specific detail view only where generic
configuration is insufficient. Provider authentication must be implemented in
Core or an approved adapter. The Web layer may proxy authenticated requests,
but must never receive access tokens or store secrets in browser storage.

## Follow-up

- Add a generic Core catalog and connection/capability contract.
- Implement OAuth callback and state validation per provider.
- Add encrypted token storage, refresh and revoked-credential handling.
- Add connection health and audit-visible reconnect/disconnect operations.
- Define plugin installation, update, signature, isolation and rollback
  lifecycle before third-party plugins are supported.

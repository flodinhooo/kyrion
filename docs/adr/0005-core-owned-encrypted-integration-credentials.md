# ADR 0005: Core-owned encrypted integration credentials

## Status

Accepted for the first official Nanoleaf integration.

## Decision

Kyrion Core owns integration connections and scopes every connection to a user
account. Provider credentials are encrypted with AES-256-GCM before PostgreSQL
persistence. The local installation key is generated on first credential use
and stored separately at `E:/Kyrion/Data/secrets/credential.key` by default;
deployments may override the path with `KYRION_CREDENTIAL_KEY_FILE`.

The browser receives only non-secret connection metadata. Provider calls and
confirmed device commands execute in Core and produce activity events. The
first supported provider is Nanoleaf's local OpenAPI; this is an official
internal integration, not a general third-party plugin runtime or public
marketplace.

## Consequences

- Connections and credentials cannot be read across Kyrion owners.
- Database disclosure alone does not disclose provider tokens.
- The key file must be protected and backed up separately; losing it requires
  pairing integrations again.
- Plugin packaging, signing, sandboxing, updates and rollback remain future
  decisions and are not implied by this slice.

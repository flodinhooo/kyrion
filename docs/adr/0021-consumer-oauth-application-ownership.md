# ADR 0021: Consumer OAuth application ownership

- Status: Proposed
- Date: 2026-09-09

## Context

Kyrion is a local-first consumer product. Requiring every installation owner
to create OAuth applications is incompatible with that product experience.
OAuth client secrets distributed with appliance hardware cannot remain secret,
while Google callbacks must also reach installations that are private or
behind NAT.

## Decision

Development keeps provider credentials in Core environment variables. They are
operator configuration and may use direct callbacks such as the current
`kyrion-node.local` URI.

Production should use Kyrion-owned provider applications and a minimal,
Kyrion-operated HTTPS callback or handoff service. The service handles the
provider-facing redirect and a short-lived, one-time, owner-bound handoff to
the initiating local Core. Long-lived access and refresh tokens remain
encrypted in that local Core. The service does not proxy ordinary provider API
traffic and does not become the credential store.

The final callback and handoff protocol require separate implementation and
security review. Direct local callbacks remain valid for development and
managed deployments where provider reachability and certificates are assured.

## Consequences

- End users have a one-click Connect experience and never configure OAuth
  client credentials.
- Local Core retains control of customer tokens and normal Calendar traffic.
- A product callback service becomes required for reliable general consumer
  deployment and must be hardened against login CSRF, replay and installation
  mix-up.
- A shipped client secret is treated as recoverable/public infrastructure, not
  as a durable appliance secret.

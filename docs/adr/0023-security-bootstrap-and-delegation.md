# ADR 0023: First-owner bootstrap and bounded delegation

Status: Accepted for the security hardening implementation.

Core remains the authority for permission checks and workspace boundaries. Role
defaults are seeded only for newly created roles, never replenished during
registration. Workspace-scoped advisory locks and database transactions serialize
role mutations, including permission checks, and roll back audit failures.
Delegates cannot grant permissions they do not possess or manage OWNER identities.

First-owner setup requires a locally provisioned, cryptographically random secret
in a protected file. Its value is supplied in a request header, never in URLs or
responses. A durable singleton initialization marker prevents reopening setup
after initialization; migration closes setup for existing accounts. Missing or
invalid secrets fail closed. Installer v1 must provision the file and transport
the secret to the operator privately. Existing installations need no setup secret.

Local calendars remain shared workspace resources; this schema does not support
personal local calendars. Explicit calendar permissions replace implicit access.
Google connections remain personal to the authenticated account. Audit entries
contain identifiers and operation codes, never appointment content or credentials.
External provider writes cannot be rolled back by a local database transaction.

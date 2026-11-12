# ADR 0054: Visible linked-installation directory and central identity labels

Status: accepted for implementation, 2026-11-12 (explicit owner request).

## Decision

Core remains authoritative for local account links. Persist only verified central
display claims (email/name) alongside the existing issuer/subject mapping. Capture
these from the validated device ID token, never from browser input or email
matching. Expose them only to that authenticated local user. Existing links are
preserved; a fresh central proof can enrich old metadata without merging users.

Add a dedicated informational installation directory to the website database.
After a local link exists, Core reports the installation/Space UUID and label,
Space type, local user UUID/name and link date. No local addresses, documents,
devices, roles, passwords or general access tokens are displayed/transferred.
The report proves its central identity using the short-lived device access token;
the website validates it by authenticated Keycloak introspection, requiring the
configured issuer, active token, website audience and official local client.

The official Keycloak deployment uses public subjects for website/local clients;
this is now an explicit provider contract for this directory, not email joining
or an assumption for arbitrary providers. Verify there is no pairwise mapper and
add a website audience mapper to the local client. Independent/pairwise providers
retain local linking; they do not implicitly opt in to this official directory.

Reports create a row scoped to the authenticated central account and return a
random per-row maintenance credential. The website stores only its SHA256 digest;
Core encrypts it with the existing credential key and contextual AAD. It permits
only updating/deleting that directory row, never local control or account access.
No provider refresh token persists in Core. Verified display claims and a durable
encrypted receipt allow metadata updates and eventual unlink reporting without
retaining broad central credentials. Retry temporary outages; local linking,
offline login and unlink never depend on directory availability.

The website labels these as confirmed links with last-report time, not online
devices or remote-control endpoints. Its authenticated session scopes every list.
Unlink reports may be delayed while the installation is offline; no directory
row grants permissions or replaces local authority.

Use a dedicated `/connect` browser entry so account settings cannot be confused
with code approval. The website account overview prominently lists installations
and offers Connect. Local Profile prominently identifies the connected central
account and synchronization state. Narrow typed APIs and polling suffice; no
webhook, inbound LAN callback or customer tunnel is required.

## Rollout and verification

Use additive website/Core migrations. Keep unrelated in-progress Core edits out
of the deployed artifact. Verify fresh schemas, existing links, user isolation,
token/receipt rejection, unlink retry, profile privacy and the real isolated
device flow before rollout. Snapshot the personal database and verify original
keys and migration compatibility before changing its running artifact.

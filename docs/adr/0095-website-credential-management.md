# Website credential inventory and removal

Status: accepted for implementation, 2026-11-24.

Extend the website BFF's existing per-user session, never administrator access.
Use the provider's own-account read API with an ephemeral user access token.
Renew and persist rotated refresh credentials under the existing session row lock,
serialize logout, and verify the signed issuer/subject before using the access
token. Return only allowlisted credential metadata, never provider payloads or
tokens. Account read permission and audience must be verified in the real provider.

Delete through supported `delete_credential:<id>` application-initiated actions,
not deprecated REST DELETE. Require website session, Origin, CSRF, explicit
confirmation, current ownership and a remaining primary login method. Bind the
selected credential ID and subject in the one-use server flow and require fresh
provider authentication. Keycloak confirms/authorizes the actual deletion and
emits its own credential events. Never delete on GET or use an admin credential.

Read-only inspection found provider event persistence disabled. Append correlated
removal start and authenticated-return observations to the existing website audit
instead of silently changing provider retention. Record the credential reference
and whether it remains visible, is observed absent, or cannot be read. Do not
interpret the untrusted action-status query as proof of deletion. The migration
extends the existing audit allowlist; runtime access remains append-only.

Show unavailable/empty/loaded states distinctly and clear stale inventory when
the website session changes. Browser password-manager synchronization cannot run
from the marketing origin for the identity origin's RP ID; do not send Keycloak
database IDs to WebAuthn Signal APIs. A removed passkey may remain in a password
manager, but the provider must reject its authentication. Treat concurrent removal
and the provider's final policy as authoritative; no blanket last-factor override.

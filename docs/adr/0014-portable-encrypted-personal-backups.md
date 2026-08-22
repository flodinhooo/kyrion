# ADR 0014: Portable Encrypted Personal Backups

- Status: Accepted
- Date: 2026-08-22

## Context

Owners need a recoverable copy of personal Kyrion data that can move to a new
installation or account. Machine-bound encryption would prevent that use case,
while exporting authentication or integration secrets would create an unsafe
credential-transfer mechanism.

## Decision

Kyrion exports a versioned JSON envelope encrypted with a user-supplied
passphrase. Version 1 uses PBKDF2-HMAC-SHA256 with 600,000 iterations and a
random 128-bit salt, then AES-256-GCM with a random 96-bit nonce. Format name
and version are authenticated as additional data.

The encrypted payload contains conversations and messages, personal-memory
settings and records, and retention policy. Derived context summaries and turn
diagnostics are omitted because they can be regenerated. Password hashes,
sessions, CSRF values, integration credentials, device tokens and private key
material are never exported.

Stable source record IDs are retained inside the encrypted payload so a future
import can resolve relationships and conflicts. Import will always assign data
to the authenticated destination owner; source ownership is not authority.

## Consequences

- The backup is portable across machines and future owner accounts.
- Losing the passphrase makes the backup unrecoverable by design.
- Export is useful now; preview, conflict planning and transactional import are
  separate follow-up slices.
- Device and integration reconnection remains explicit.

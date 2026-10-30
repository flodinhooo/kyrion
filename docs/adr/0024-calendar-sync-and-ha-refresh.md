# ADR 0024: Explicit calendar synchronization and refreshed HA snapshots

Accepted 2026-10-19 for this recovery implementation.

The existing local calendar remains independent. Google synchronization is an
explicit per-event opt-in to a selected calendar, never an export of all local
events. Core persists remote identity, version and pending operations. Reads do
not write external events. An authenticated manual sync retries pending work;
conditional writes detect external changes and preserve conflicts for review.
Deleted local synchronized events remain as tombstones until remote deletion is
confirmed. Imported recurring instances and all-day events remain read-only.
Provider failures must be distinct from an empty calendar.

Google access remains personal to the authenticated account. Shared local events
must not be exported by another user. Existing credentials remain encrypted.
Synchronization runs only when explicitly requested by a user with all required
calendar mutation permissions. No background external writes are introduced.

HA retains ADR 0018's read-only snapshot protocol, stable identities, bounded
mapping, and serialized reconciliation. A Core scheduler refreshes configured
owners using that same importer before the 60-second observation TTL expires.
Manual device refresh uses the same importer. Connection failures preserve cached
readings with an explicit diagnostic; they do not prove physical-device failure.
Provider measurement timestamps and Core observation timestamps stay separate.
No second WebSocket ingestion path or new HA control authority is introduced.

This extends the read-only Google display handoff and explicit-only HA refresh
documented previously. It does not establish physical hardware acceptance.

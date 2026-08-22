# ADR 0015: Owner-Scoped Audit Integrity Chains

- Status: Accepted
- Date: 2026-08-22

## Context

Owner-scoped activity history is useful only if Kyrion can detect silent edits,
reordering and deletion. A plain database hash is insufficient because anyone
with write access could recompute it. Retention must also remain possible
without making an authorised cleanup indistinguishable from tampering.

## Decision

Core seals every new activity event with HMAC-SHA-256 using a dedicated local
32-byte integrity key. The canonical input includes all persisted event fields,
the owner or system chain scope and the preceding event hash. PostgreSQL chain
heads are locked while an event is appended, so concurrent writes cannot fork a
chain. Existing rows remain explicitly reported as unsealed legacy events.

The authenticated integrity endpoint recomputes the owner and system chains,
checks every link and event hash, and compares the result with the locked chain
head. It returns stable issue codes without exposing hashes or key material.

Authorised activity retention may remove only a chronological chain prefix.
Before deletion, Core stores an HMAC-authenticated previous-hash anchor. This
allows verification to distinguish an approved prefix prune from an arbitrary
gap. Non-prefix pruning is rejected.

## Consequences

- Direct modification, reordering or unapproved deletion of sealed events is
  detected while the integrity key remains trustworthy.
- The integrity key is separate from integration credential encryption and must
  be backed up through protected secret-management procedures.
- Losing the key makes historical verification unavailable. An attacker who
  controls both the database and the key can forge history, so this mechanism
  alone is not a compliance certification or an external transparency log.
- Future high-assurance deployments may periodically anchor chain heads in a
  separately administered or append-only system.

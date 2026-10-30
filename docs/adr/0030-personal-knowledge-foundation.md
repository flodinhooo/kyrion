# ADR 0030: Personal knowledge through Core and K-AI

Status: accepted for K-Data M01 implementation.

Core owns documents, actor-scoped access, local original files, persistent leased
ingestion jobs and retrieval. Existing K-AI remains the only generation path.
Personal ownership uses authenticated user identity, never shared workspace
ownership; installation administrators have no private-knowledge override.

The active checkout has no canonical organization schema. The domain reserves
ORGANIZATION, but the database and APIs accept PERSONAL only. A later additive
migration must reference the canonical organization table after Spaces lands.
No placeholder organization UUID or duplicate organization table is introduced.

Existing PostgreSQL 17 Alpine installations lack pgvector. Changing their image
or requiring an extension would complicate safe upgrades. M01 stores validated
real arrays and computes exact cosine similarity over owner-authorized rows in
PostgreSQL. This is a small-index alternative, not an approximate vector index.
The retrieval boundary can later use pgvector without changing public contracts.
One configured embedding model and dimension selects the active index; changing
either excludes old chunks until explicitly reindexed. There is no cloud embedding
adapter or fallback. Ollama is used only through a narrow local embedding client.

PDFBox is a new dependency because the repository has no PDF parser. Parsing
runs in a separate JVM with a bounded heap, elapsed-time deadline, page and text
limits. It extracts text only, never renders or executes embedded content.
Plain text must decode strictly as UTF-8. Scanned/empty PDFs fail explicitly.

Document context is explicit per request, bounded, and untrusted. Under the
existing current-message-only cloud policy, knowledge-enabled requests require
a local generation model and local fallbacks. Consent behavior for ordinary
cloud chat remains unchanged. Sources are emitted with the assistant message ID
and stable document/revision/chunk references; provider-generated citations are
not treated as verified sources. Velora shares the orchestration entry point.

Jobs use PostgreSQL leases and fencing tokens. Publication locks the document,
checks the live revision and lease, and replaces chunks atomically with READY.
Deletion first tombstones the document, preventing retrieval and publication;
scheduled cleanup then removes originals and index rows. Old unreferenced files
are swept after a grace period to recover upload/transaction crashes.

Backups must capture the database and document root while Core is stopped.
Database-only personal export is not a knowledge-file backup. Original files and
database metadata are private and require protected storage and encrypted backups.

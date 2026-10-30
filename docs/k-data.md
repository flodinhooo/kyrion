# K-Data M01: personal knowledge

Core's `knowledge/{domain,application,persistence,storage,ingestion,api}` and
`context/KnowledgeContextAssembler` implement personal ingestion and retrieval.
All product experiences use this same foundation. See [ADR 0030](adr/0030-personal-knowledge-foundation.md).

## Local setup

Build Core with Java 21 using `gradlew.bat test bootJar`; this also builds
`build/libs/knowledge-parser.jar`. Keep the parser beside the deployed app and
set `KYRION_KNOWLEDGE_PARSER_JAR` if running outside the Core project directory.
No Python parser, OCR, cloud embedding or new service is installed.

Configure these operator-owned values (never browser input):

| Variable                               | Default                           | Meaning                                                     |
|----------------------------------------|-----------------------------------|-------------------------------------------------------------|
| `KYRION_KNOWLEDGE_ROOT`                | `./data/knowledge`                | Persistent private original files                           |
| `KYRION_KNOWLEDGE_MAX_BYTES`           | `10485760`                        | Upload byte limit (maximum 50 MB)                           |
| `KYRION_KNOWLEDGE_PARSER_JAR`          | `build/libs/knowledge-parser.jar` | Bounded PDF parser process                                  |
| `KYRION_KNOWLEDGE_EMBEDDING_URL`       | `http://127.0.0.1:11434`          | Local Ollama HTTP runtime                                   |
| `KYRION_KNOWLEDGE_EMBEDDING_MODEL`     | empty                             | Explicit installed embedding model, e.g. `nomic-embed-text` |
| `KYRION_KNOWLEDGE_EMBEDDING_DIMENSION` | `768`                             | Required actual vector dimension                            |

Install the chosen embedding model on the operator-controlled runtime separately.
This configuration is independent of the conversational model registry. Empty
configuration fails ingestion with `KNOWLEDGE_EMBEDDING_SETUP_REQUIRED`; an
unavailable model fails explicitly, with at most three transient attempts.
No model is downloaded automatically. Endpoints must resolve to loopback or
private network addresses. Redirects, public hosts and cloud fallback are denied.
Only trusted operators may configure DNS/runtime endpoints.

The node and installer Compose templates mount `/var/lib/kyrion/knowledge`.
Prepare the bind directory owned by UID/GID 10001 with mode 0700 before startup.
The installer still does not install AI: configure an accessible local runtime
explicitly; container loopback refers to that container, not the host.
The Windows development Compose runs PostgreSQL only; Core uses its configured
host document directory. Keep that directory outside source control. Startup
checks directory creation; missing parser/model errors are surfaced on use rather
than preventing essential non-AI Core functions from starting.

## API and privacy

Core uses `/v1/knowledge`; Web proxies `/api/knowledge` with the existing session
and CSRF mechanisms. There are no client-provided owner identifiers.

- `GET/POST /spaces`: list or idempotently create the actor's personal space.
- `GET /spaces/{id}/documents?limit=50&offset=0`: bounded owner-only listing.
- `POST /spaces/{id}/documents`: multipart field `file`, PDF or strict UTF-8 `.txt`.
- `GET /documents/{id}`: safe metadata, never storage keys or vectors.
- `GET /documents/{id}/content`: authenticated attachment, no-store/nosniff.
- `DELETE /documents/{id}`: immediate retrieval tombstone, eventual disk/index cleanup.
- `POST /documents/{id}/reindex`: invalidate the previous revision and queue a new one.
- `POST /search`: `{spaceIds: [UUID], query: string, limit: 1..5}`.
- `GET /answers/{conversationId}`: actor-scoped references for saved answers.

`knowledge:read/create/delete` follow existing RBAC conventions. Permission alone
never bypasses personal ownership, including installation OWNER/ADMIN roles.
Foreign document and space identifiers return the same 404 as unknown resources.
Organizations are a domain enum only until the canonical Spaces schema and
membership authorization are integrated. No organization controls are exposed.

Originals are validated before queue acceptance. PDFs run in a separate JVM (128 MB heap, 64 MB metaspace, 20 second
deadline), limited to 200 pages and
bounded extracted text; encrypted/malformed and scanned/no-text PDFs fail.
PDFBox only extracts text; it does not render, execute scripts, follow links or
fetch external resources. The parser is resource-isolated, not an OS security
sandbox; keep PDFBox patched and restrict the Core service account.
One ingestion worker per instance batches eight chunks; database leases prevent
competing publications. Pending work survives restarts; expired leases can be
reclaimed, with a maximum of three attempts and fencing on publication.

Chunks use normalized page-local offsets, 2,000 characters with 200-character
overlap (~500 tokens; estimates are not tokenizer counts). A document is READY
only after complete transactional publication. Up to 100 documents per personal
space and 600 chunks/document bound the initial exact-search workload. PostgreSQL
real arrays provide exact cosine retrieval with an authorization-materialized
candidate set. There is no pgvector deployment prerequisite or lexical fallback.
Only the configured model/dimension is searchable. After changing either,
explicitly reindex existing documents. Reindexing temporarily hides the previous
index and never mixes old/new chunks. A failed revision exposes no partial index.

## Chat and Velora

Enable the personal-knowledge toggle in existing chat. Core retrieves at most
three authorized excerpts into a bounded budget, then calls the existing K-AI
router/provider path. Retrieved JSON is quoted source data, never a system prompt.
Tool events remain rejected by the generation surface. Cloud knowledge is denied
even with ordinary cloud consent because the existing policy releases only the
current message. Ordinary cloud chat consent and streaming contracts remain.
Core's shared voice orchestration accepts the same optional knowledge flag;
the satellite audio pipeline and its session controls are unchanged.

`knowledge.sources` NDJSON events carry the assistant message ID and stable
`kd:documentId:revision:chunkIndex` references. Only retrieved sources appear in
the source list; model-generated citation text is not verification. Successful
answers persist references without copying excerpts. Sources can be downloaded
after reloading a conversation; deletion removes saved reference rows. Already
generated conversation text remains subject to existing conversation deletion.
Prompt instructions reduce injection risk but cannot prove semantic LLM obedience;
Core enforces identity, local-only routing, tool denial and authorization outside
the model regardless of generated text.

## Backup, restore and upgrades

Migrations are additive; PostgreSQL image and existing tables remain unchanged.
Build and distribute both application and parser jars. Preserve existing data
volumes and credentials. Do not run this work against production automatically.

For a consistent backup, stop Core, create the existing PostgreSQL dump, then copy
the entire configured document root into the same protected backup set. Include
checksums and the configured embedding model/dimension in a private manifest.
Encrypt and restrict both components; neither alone is a complete backup. Existing
personal JSON export does not include documents. Back up audit/credential keys
separately under the existing secret-storage policy.

Restore into isolated directories/database first. Verify checksums and parser
availability, apply Flyway, point Core at the matching restored file root and
database, and verify owner isolation/download/search with disposable accounts.
Pending/expired jobs resume; READY chunks need the same embedding configuration.
Never restore only old files over a live database. Test restore before promotion.
Unreferenced files and interrupted temporary uploads older than 24 hours are
swept; tombstones retry cleanup until successful.

M02 candidates: canonical organization ownership, membership-aware retrieval,
pgvector scale measurements, richer extraction/provenance, operational job UI,
and encrypted portable knowledge export with a verified restore drill.

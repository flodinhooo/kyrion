# ADR 0080: Consented model operations on a selected loopback Ollama runtime

Status: Accepted for implementation, 2026-11-14.

Extend ADR 0075's explicitly selected local runtime. Use the existing authenticated
model catalog, installation lock/authority and protected journal. No alternate
model/account/Space registry is introduced. Pull review includes exact tag,
manifest digest, size, license and estimated resource needs. Unknown external
model-store capacity stays unknown. No generation, cloud fallback or automatic
startup download follows selection or model installation.

Before a pull, authenticate the registry manifest through the existing verified
HTTPS transport and catalog hash/size pins. Never overwrite a pre-existing tag
whose digest differs. POST only the reviewed model and stream flag to the
selected literal loopback endpoint. Parse bounded progress records with absolute
deadlines, never display raw provider error/status strings. Journal intent before
mutation. Disconnection is an interruption, not successful completion; an explicit
repeat can reuse Ollama's partial cache. Only a matching post-operation model
inventory permits a completion receipt. Runtime-reported hashes are observations,
not independent verification of an unmanaged runtime's files or identity.

Removal requires separate explicit review of the current exact model/digest,
including its possible use by other applications. Refuse currently loaded models.
Never remove an unreviewed model, foreign runtime, configuration or service.
Post-operation inspection confirms disappearance. A retry after interruption
can reconcile only the same intended inventory change; unrelated changes require
another runtime selection/review. No background retry silently grants consent.

The official [pull API](https://docs.ollama.com/api/pull.md),
[delete API](https://docs.ollama.com/api/delete.md) and
[model inventory](https://docs.ollama.com/api/tags) were checked on 2026-11-14.
The existing Qwen3 0.6B Q4_K_M catalog pin still corresponds to the
[official variant](https://ollama.com/library/qwen3:0.6b-q4_K_M).
Managed runtime installation, resource configuration, actual AI activation and
authenticated cross-device access remain separate binding source requirements.

The actual 0.40.16 file test must distinguish the runnable v2 manifest from the
legacy downgrade anchor described by
[WriteLegacyAnchor](https://github.com/ollama/ollama/blob/v0.40.16/manifest/manifest.go).
Only exact pinned runnable bytes and their content-addressed blobs establish the
fixture's independent file check; an equivalent-looking JSON document is not a
substitute for a matching digest.

# ADR 0048: curated model recommendations use the existing signed-document trust

Status: accepted for implementation, 2026-11-11.

The installer recommendation catalog is a versioned data document, not another
AI registry or permission system. Core remains authoritative for active model
profiles, providers, budgets and inference policy. A recommendation never
activates cloud processing, downloads a model or changes an existing runtime.

The initial reviewed catalog contains exact Ollama tags, full registry manifest
digests, config-plus-layer byte totals, license/source links and explicitly
estimated memory requirements. A reviewed catalog is bundled with the installer.
Updated catalogs must use the scoped `model-catalog` Ed25519 envelope and trust
store already implemented in `release_policy.py`; expiry and monotonically
increasing catalog sequence prevent replay. Production trust/signing is a
release prerequisite, not a fabricated key checked into the repository.

Recommendations use observations from the intended execution target, user
purpose/language/priority and an explicit memory budget. Unknown RAM, free disk,
architecture or CPU count cannot become invented capacities. Reserve resources
for the OS, Kyrion and concurrent work/gaming. A GPU name or driver is not proof
of usable inference acceleration. Until runtime evidence exists, estimate a CPU
execution path and do not promise latency or tokens per second.

Official sources checked 2026-11-11:

- https://ollama.com/library/qwen3:0.6b
- https://ollama.com/library/qwen3:4b
- https://registry.ollama.ai/v2/library/qwen3/manifests/0.6b
- https://registry.ollama.ai/v2/library/qwen3/manifests/4b
- https://docs.ollama.com/api/pull.md

Only small registry metadata was downloaded during development; no model or
paid provider call was made. Memory values are conservative planning estimates,
not hardware benchmark results. Full Ollama lifecycle integration remains a
separate requirement and must not be implied by recommendation output.

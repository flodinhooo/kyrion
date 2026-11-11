# Installer model recommendation data

`infrastructure/installer-v1/models.py` is a planning function using actual
execution-target observations from `host.py`. It does not replace Core's model
registry, inference policies or provider budgets. `--recommend-ai` and the
optional terminal setup step collect purpose, DE/EN language needs, priority,
concurrent work/gaming and a whole-GiB memory budget. The normal installation can
skip the step and run without AI.

The recommendation reports its target observations, actual effective budget,
reserves, exact variant, sources, license and estimated context/memory. RAM and
disk must be known, architecture recognized and CPU count observed. Unknown
capacity yields no recommendation. Memory reserves are at least 3 GiB or 20%
for the OS, 2 GiB for Kyrion, and another 2/4 GiB for work/gaming. The explicit
budget is an additional upper bound. Disk retains one extra model-sized staging
copy plus 1 GiB. These are conservative planning rules, not benchmarks.

The reviewed 2026-11-11 catalog contains Qwen3 `0.6b` and `4b`, Q4_K_M,
Apache-2.0. Official HTTPS registry manifests were fetched without model blobs.
Config-plus-layer sums are 522653767 and 2497293931 bytes respectively. Manifest
digests and actual official license/source URLs are stored in the catalog.
The 2/6 GiB memory estimates refer to a 2048-token planning context, without a
speed promise. Coding excludes the smallest variant. CPU is the conservative
execution estimate; an NVIDIA name or driver does not prove inference offload.

The bundled reviewed document inherits trust from the eventual signed native
distribution. Current development executables remain unsigned. An external
catalog is accepted only as an Ed25519 `model-catalog` envelope using the existing
trust policy, with expiry and caller-supplied minimum sequence checks. For a
developer invocation use `--recommend-ai --model-catalog <envelope>
--trust-store <trusted-public-store> --minimum-catalog-sequence <accepted>`.
Production feed fetching, persisted accepted-catalog sequence and release root
distribution remain open in matrix R48. Do not claim automatic authenticated
catalog updates from this loader alone.

Recommending a model does not download it or change Ollama settings. Runtime
installation/adoption, hash-verified model pull, active Core profile selection,
benchmark and model removal remain separate open requirements. No cloud fallback
is enabled by planning. When no recommendation fits, setup can continue without
AI; choosing another execution device or optional cloud needs its own explicit
flow and policy checks.

Official sources are recorded in [ADR 0048](adr/0048-installer-model-recommendations.md).

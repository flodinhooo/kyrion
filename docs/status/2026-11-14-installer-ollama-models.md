# Consented model download, interruption and removal

The full installer assignment remains open. ADR 0080 extends the existing local
runtime selection and authenticated model catalog. Installed maintenance accepts
`--ollama pull --ollama-model qwen3:0.6b` and
`--ollama remove --ollama-model <exact-local-model>`, using the selected runtime.
Neither command installs Ollama, connects Kyrion AI or enables cloud inference.

Pull authenticates the official registry manifest through verified HTTPS and
the catalog hash/size pins before large transfer. Review includes exact variant,
size, license, source and resource estimates; unknown external store capacity
stays unknown. A conflicting existing tag is refused. Bounded NDJSON progress,
absolute deadlines and persisted intent distinguish interruption from completion.
Explicit repeat reconciles a completed but unacknowledged operation or lets
Ollama reuse partial data. No background download grants consent.

Removal has separate review of the exact current model/digest and possible use
by other applications. Loaded models, including digest aliases, are refused and
checked again after confirmation. Only the reviewed model is selected for
deletion. Final inventory must show the intended change and unchanged unrelated
models. Runtime version/scope/inventory changes require renewed selection;
provider error/status text is never rendered or persisted as an error message.
`--ollama status` includes the validated operation journal.

## Evidence

- Full suites: 468 Windows tests (eight skips), 475 isolated Debian tests (twenty
  skips). Nineteen new model-operation fixtures use real TCP/HTTP and journals
  with synthetic Ollama/registry responses. They cover cancellation, registry
  source mismatch, conflicting tags, interrupted streams, lost acknowledgements,
  malformed/error/oversize/redirect responses, slow headers, missing models after
  claimed success, loaded-model races, unrelated changes and authority refusal.
- Both current official Qwen3 registry manifests still match the existing pins
  and exact config/layer sizes. Evidence:
  `build/ollama-official-model-manifests-20261114.json`.
- Actual Windows Ollama 0.40.16 test uses a copied hash-checked executable with
  valid Ollama Inc. Authenticode, a new protected user/System fixture, verified
  TCP owner and isolated home/model directories. The ordinary installed runtime
  and user models are untouched. Its host installation/admin checks are adapted
  explicitly; this is a developer process fixture, not SCM acceptance.
- Actual `qwen3:0.6b` Apache-2.0 download is 522,653,767 bytes. The stream is
  deliberately interrupted at 8,560,576 reported bytes. A real partial cache and
  interrupted journal are observed. The explicit repeat begins at the same byte
  count, completes, and all runnable-manifest/config/layer file hashes are checked
  independently in this known private fixture. The single model is then removed
  through the real API. No generation, benchmark or AI activation occurs. The
  runtime is stopped through its contained process job.
  `build/ollama-probe-db6af248d4dd43e38e34996559e5ba7c/report.json` and
  `build/ollama-model-real-download-final-test.txt` record this evidence.
- The initial independent file check failed because it selected Ollama's legacy
  downgrade anchor, which intentionally includes an extra manifest-reference
  layer. The verified executable's [versioned source](https://github.com/ollama/ollama/blob/v0.40.16/manifest/manifest.go)
  distinguishes that file from the runnable v2 manifest. The corrected test
  requires exact pinned bytes for the runnable manifest and exact blob hashes;
  it does not normalize away a hash mismatch. The failed initial fixture remains
  unaccepted, with its test-only data preserved.
- Native development `.20261114.17` packages pass source/artifact hash matching,
  executable/resource smoke and workflow validation. Windows EXE: 12,770,829
  bytes, SHA-256
  `fd7d0b02003565cba5bff79c56f719635d486e56def1d31581d55c883c170f97`.
  Linux AMD64 archive: 14,577,376 bytes, SHA-256
  `1090a4809cb37ac1b72c9897d157eae65b0cbdc39dee569b2b85f0bf8136d8c5`.
  Files/metadata are under `build/native-installer/`, unsigned, unpublished and
  explicitly `platformInstallationAccepted: false`.

For unmanaged runtime operations, completion uses runtime-reported inventory
digests and explicitly reports `independentBlobVerification: false`. Only the
known-path developer fixture independently reads model files. Restart of the
Ollama process or host is not claimed by the partial-cache test. Actual Linux
Ollama runtime acceptance remains outstanding; Linux HTTP/state tests are real
local transport with synthetic provider data.

Managed runtime installation/autostart/resource configuration, AI model
activation/switch, benchmark, authenticated multi-device access, Velora and the
other ledger gaps remain source work. No partial user test is requested.

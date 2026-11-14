# Protected existing-agent enrollment and local transport

The full installer scope remains open. This checkpoint implements the existing
Linux gateway agent's prepared enrollment; it does not complete installer device
deployment, Windows agents, task roles or distributed updates/moves.

## Implemented behavior

The existing CLI gains `enroll-prepared`. A protected owner-only file supplies
the one-use code; no web password or code is placed in process arguments. Under
an exclusive lock, the agent durably publishes its random credential, original
identity/version, target and trust binding before making its first request.
Pending state survives a failed process or lost response. Core protocol 2 is
checked before sending the code, and its existing acknowledgement contract
returns the same node. Final `agent.json` publication precedes pending cleanup.
A resumed cleanup does not contact Core again. Existing identities, different
target/code/trust and public/symlinked secret files fail rather than overwrite.
Expired/rejected pending registration is preserved for authorized maintenance;
there is no automatic re-pairing or completed guided recovery for that case yet.

Prepared transport requires verified HTTPS and hostname checks. A selected local
CA is copied privately and its exact bytes pinned for subsequent authenticated
requests. It refuses redirects/proxies, resolves once per connection, rejects
mixed/public answers, connects the checked numeric address and verifies its
peer. Supported address ranges are explicit RFC1918/IPv4 loopback and IPv6
ULA/loopback; public/global-IPv6/link-local addresses are refused. Responses have
a size bound. Legacy explicit HTTP configuration is retained without automatic
rewrite. No new runtime dependency or separate identity/Space store is added.

The existing reference unit bounds process crashes to three starts per five
minutes. Its syntax is verified, but it was not installed or started here. The
permissions document's stale initial deferred-slice wording is corrected to
match the already existing executable/unit; no deployed account/unit changed.

## Evidence

- Full gateway suite: **40 tests pass on isolated Linux**, including actual TLS,
  real Linux metrics, private file/lock checks, interruption/restart, competing
  local attempts, destination changes, immutable existing config, DNS/peer
  refusal and redirect/size limits. HTTP is injected only in the lifecycle unit
  tests; transport tests use real loopback HTTP/TLS with synthetic Core data.
- Windows gateway suite: **29 pass, eleven skips**. Ten prepared Linux-storage
  tests and the existing Linux-metrics test are explicitly skipped. Actual
  Windows TLS/socket and shared transport tests run; this is not Windows agent
  storage/service acceptance. Ruff and changed-file formatting pass.
- `verify-agent-enrollment.py` passes against actual schema50 Core/PostgreSQL and
  separate agent CLI processes inside the isolated namespace. The first request
  commits at Core, then a deliberate after-response loss is injected. A new
  process resumes the same private identity. Exactly one node and one audit
  event exist, the stored credential authenticates an empty command poll, and a
  changed CA is refused. No raw credential enters child output. There are no
  household commands, hardware actions or service/permission probe injections.
  Evidence: `build/isolated-linux/agent-enrollment-report.json`,
  `agent-enrollment-run.txt`, `gateway-full-tests.txt` and
  `gateway-enrollment-unit-run.txt`.
- The manual isolated Linux CI workflow now runs this test and exports only its
  public report. YAML/step structure is validated locally; hosted execution was
  not triggered or claimed. Existing Python CI runs the full gateway suite.
- Development wheel and sdist build successfully in an isolated build-tool
  environment. The wheel contains the exact current new source modules and its
  CLI help exposes the new mode. Wheel: 19,977 bytes, SHA-256
  `b8b9632f4d414a6bd43afe8cc98850bd5f3bdb3ec1e3a967ac2344fb4001f284`.
  This is an unpublished Python developer artifact, not the required end-user
  node distribution. Existing native installer `.25` artifacts and their source
  hash checks are recorded separately in the Core enrollment checkpoint.

Continue with existing-node revocation/metadata/task assignment, installer
pairing/account/Space wiring and least-privilege supported Windows/Linux agent
deployment. Missing implementation remains source work, not an external hardware
blocker. No partial user test is requested.

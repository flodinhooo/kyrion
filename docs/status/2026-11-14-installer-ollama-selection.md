# Local Ollama inspection and explicit selection

The overall installer assignment remains open. R50 is not complete: this change
implements working local inspection and persistent selection, not managed runtime
installation, model pulls, Core/AI activation or distributed inference.

`--target TARGET --ollama status` inspects the selected instance (default port
11434 when none is selected). `--ollama select --ollama-port PORT` reviews and
selects an existing instance after host-administrator and installation ownership
checks. DE/EN prompts distinguish selection from actual Kyrion AI connection.
External configuration, services and existing models are not modified.

Actual IPv4/IPv6 listener tables are read on the execution host: Linux proc tables
or Windows GetExtendedTcpTable. Wildcard/nonlocal, missing or unknown listeners
are refused. HTTP uses literal IPv4 loopback without environment proxies or
redirects. Replies have bounded bytes/counts, strict normalized fields and a
shared absolute socket-read deadline; slow headers cannot reset it. Provider
error payloads are not logged. Runtime-reported VRAM is an observation, not proof
of benchmarked or usable acceleration.

Selection reviews version, scope and catalog, probes again after approval and
refuses changes. Only approved endpoint/version/hash/time enter the private
journal. Status separates historical selection, live availability and snapshot
agreement. Offline/changed instances preserve progress without false health.
Retired authority, restore and update fences precede requests. Cancellation
retains progress. No inference/download/cloud action is activated; an external
runtime's cloud configuration remains explicitly unknown.

## Developer evidence

- Thirteen tests use real local TCP tables, IPv4/IPv6 sockets, HTTP and private
  journals with synthetic Ollama replies. Host-administration checks are injected
  in journal tests. Rejections cover wildcard/nonlocal fixtures, malformed,
  duplicate/oversized replies, redirects, changed catalogs, cancellation, offline
  instances, stalled/dripping HTTP and maintenance fences.
- Complete suites: 423 Windows tests (three skips), 425 isolated Debian tests
  (sixteen skips); Ruff/format checks pass.
- Actual Windows Ollama 0.40.16 CLI/API probe passed with a new test copy of a
  valid Authenticode-signed Ollama Inc. executable, SHA-256
  `4ccefcbfecc50fb6526471adabbc20869dd614e29e351120b15083cb174b0b8a`.
  A protected current-user/SYSTEM fixture, empty home/model directories, explicit
  loopback port, minimal environment and disabled cloud setting were used. The
  listener PID matched the owned job process. Version and empty model/running
  lists were genuinely queried; the own process was stopped and listener removal
  verified. No existing runtime/model was used or changed. Evidence:
  `build/ollama-probe-b55f7a4558f34750910cfcd9295b47b4/report.json`.
  This is not native SCM/system-boot or GPU-generation acceptance.
- Native `.20261114.11` developer packages in `build/native-installer/` remain
  unsigned/unpublished/platform-unaccepted. Windows EXE: 12,738,845 bytes, SHA-256
  `c5b4b24c5cf6fc3a85c113d972002aaa54f056e215abafab02ac3a0799021706`.
  Linux AMD64 archive: 14,544,012 bytes, SHA-256
  `a8347b5e3988b39e8a55ef2bf0acb2cb23a88d7fc868d6de28c709ef85a87193`.

ADR 0075 records official API/OS sources. Managed runtime distribution,
model lifecycle, existing Core/AI activation, hardware-backed benchmarks,
authenticated cross-device access and local Web management remain source work.
This is not overall user-test readiness.

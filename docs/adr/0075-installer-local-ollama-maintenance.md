# ADR 0075: Explicit local Ollama runtime maintenance

Status: Accepted for implementation, 2026-11-14.

Reuse the installation's protected host-admin journal and existing model catalog.
The installer may inspect/select a local Ollama runtime and later manage approved
runtime/model resources. This is operational configuration, not another AI model
registry, account system or inference authorization path. Core and the existing
AI service retain model/provider, budget and execution policy ownership. Selecting
a runtime alone must never claim that Kyrion inference has been connected.

For an existing instance, use a literal loopback address, bounded direct HTTP
without DNS, environment proxy inheritance or redirects. Inspect actual IPv4 and
IPv6 listeners on the execution target; reject wildcard/nonloopback or unknown
bindings. Confirm the normalized live version/model snapshot before selection,
probe again after approval, and persist only a matching result. A selected external
runtime is explicitly unmanaged: no service/configuration overwrite or automatic
model/runtime removal. No generation, pull, cloud call or microphone action is
part of discovery/selection. Loopback scope is not cryptographic process identity.

Later signed optional runtime distribution, exact reviewed model downloads,
synthetic benchmark and existing Core/AI activation require separate working
paths and explicit consent; this decision does not label them implemented.
Cross-device runtime access must use the authorized device-agent boundary, never
an unauthenticated Ollama LAN port.

Official contracts reviewed 2026-11-14: [models](https://docs.ollama.com/api/tags.md),
[running models](https://docs.ollama.com/api/ps.md),
[server version route](https://github.com/ollama/ollama/blob/main/server/routes.go),
[Windows TCP tables](https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getextendedtcptable),
[IPv6 row layout](https://learn.microsoft.com/en-us/windows/win32/api/tcpmib/ns-tcpmib-mib_tcp6row_owner_pid).

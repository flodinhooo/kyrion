# ADR 0088: Reviewed transition of existing local agent ingress

Status: Accepted for implementation

## Decision

Extending an installed proxy is an installer maintenance transaction, not a side
effect of issuing a pairing code. Reuse the existing root-owned journal and
installation lock. Accept only exact known managed proxy definitions; preserve
custom/changed content. Keep the existing listener, certificate and hostname.
Expose only the existing local-peer agent allowlist, with Core authentication and
Space permissions unchanged. Do not open ports, install new runtime software or
download images as part of this operation.

New activation/resume requires a current linked Core identity with authoritative
`system_settings:update` and `gateways:create` permissions, in addition to local
OS administration. Core's local capability endpoint must prove compatibility.
Record the approving identity, Space, transaction UUID, host binding and exact
before/after configuration in the protected journal, never a session credential.
The installer retains OS deployment authority; it does not add a browser/AI API
for privileged commands or replace Core's device-action policy.

Validate with the actual retained Caddy runtime before publication. Journal the
intent before stopping/replacing anything. Restart only the owned proxy and test
the actual pinned local TLS agent endpoint. During an incomplete transition,
ordinary installation/update/startup operations remain fenced. Resume accepts
only the recorded before/after bytes, never arbitrary current file contents.

An active Linux transaction temporarily uses installer journal format 2. The
current reader accepts it only for the explicit active transaction phases;
ordinary operations remain fenced. Older format-1-only installers consequently
refuse even if they predate the named fence. After verified activation or recovery,
the journal returns to format 1 with completed metadata. This is a local installer
compatibility barrier, not a database schema upgrade/downgrade. It does not replace
the installed-worker capability checks or stop an uncooperative OS administrator.

Before opening a transaction, execute each enabled, owned, integrity-checked
installed maintenance worker's read-only capability check. It must advertise the
new ingress fence. A source update or newly downloaded installer does not upgrade
an older scheduled executable. Refuse before changes when an enabled old worker
cannot honor the fence; use the existing installer maintenance-worker upgrade
paths first. Disabled old workers do not establish active runtime support.

An explicit local-root recovery may restore only the previously approved known
configuration even if Core is unavailable after interruption. This is restoration
of prior OS state, not a fresh grant of network/device authority. Record root
recovery separately from the original Core approval. A verified TLS listener after
recovery is not proof that Core, the web app or all devices are healthy.

Implement and test the Linux Compose transaction first. Native Windows service
activation requires its own complete adapter and actual/elevated acceptance;
do not classify missing adapter code as a hardware-only test limitation.

Official references checked before implementation:
[Caddy CLI validation and stdin configuration](https://caddyserver.com/docs/command-line)
and [Compose recreation without dependency startup or image pull](https://docs.docker.com/reference/cli/docker/compose/up/).

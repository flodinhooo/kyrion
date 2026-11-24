# ADR 0092: Preserve unknown prepared-node health

Status: Accepted for implementation

Windows prepared agents must never report unimplemented Linux probes as negative
hardware facts. Extend the existing health contract with explicit nullable
throttling, interface presence/connectivity, IPv6 and Bluetooth observations.
Existing boolean payloads and persisted health remain readable. The local UI
renders a translated visible unknown value, including in assistive technology;
do not hide uncertainty in color, tooltips or screen-reader-only text.

Advertise health-unknown protocol 1 on the existing enrollment capabilities
endpoint. Before submitting a health payload with unknown booleans, prepared
clients require that capability over their pinned local TLS transport. Older
Core must not silently coerce null to false. Coordinate Core and local Web in
published release compatibility metadata before shipping an agent using it.
This source change is not a published release or an old-client compatibility
claim for newly nullable payloads.

Use actual GlobalMemoryStatusEx and disk usage on Windows. Unimplemented thermal,
network, Bluetooth and attached-hardware probes remain unknown/unobserved; do not
launch Linux commands or activate microphones. Unknown OS service health does not
negate an authenticated recent heartbeat, which still proves agent reachability.
Resource probe failure is an error, never fabricated capacity.

No schema migration is necessary: health is existing JSON. This does not enable
Windows foreground/task runtime or SCM deployment by itself. Verify nullable
round trips in Core/PostgreSQL, strict browser parsing/rendering and actual
Windows resource APIs separately from controlled protocol and platform doubles.

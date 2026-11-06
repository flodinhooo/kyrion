# Gateway queued-command authority

This source slice implements [ADR 0036](adr/0036-gateway-command-authority.md).
Verification and delivery evidence are tracked in
[the Assignment B results](agent-handoffs/2026-11-06-gateway-authority-results.md).
It does not authorize deployment or establish physical acceptance.

## Authority and dispatch

`gateway_command.owner_id` remains the resource Space compatibility key. It is
never an execution principal. A separate typed `authority` JSON document captures
principal kind and ID, Space, required permission, capability, and applicable
grant/session/source-node/target-connection IDs. Correlation remains separate.
Only Core creates this document; browser bodies, model proposals and node payloads
do not provide it. No credentials or session tokens are stored in the document.

Every enqueue/await/confirmed-execution API requires a `GatewayAuthority` argument.
Human HTTP callers construct it using the authenticated request's user and Space.
Web action services also require the explicit actor, with no owner default.
The Action handler carries server-created human, automation or Voice provenance
into device commands. AI is a proposer, never an execution principal.

At enqueue Core resolves the original integration connection for device commands,
then validates Space, current principal authority, node ownership, permission and
capability. Current catalog capabilities are checked again at release, so a target
reconfigured from a light into a sensor cannot retain an old power command.
At claim Core authenticates the node and atomically claims a pending
row with `FOR UPDATE SKIP LOCKED`. Before releasing the payload it rechecks the
persisted authority, target identity and current node device observation. A removed
device recreated at the same address does not inherit the old command.

Denied claims commit a terminal `failed` result with `AUTHORITY_REVOKED`, or
`AUTHORITY_PROVENANCE_MISSING` for missing/unreadable provenance, and a correlated
denial event attributed to the original principal where known. No payload reaches
the node. A suspended Space blocks authentication/polling before claiming; its
pending rows remain pending until it becomes active or an operator cancels them.

Human commands are durable accepted intent. Logout/expiration blocks new HTTP
requests; already accepted commands remain conditional on current membership,
enabled status, Space eligibility and permissions. Role or account revocation
therefore blocks dispatch. Space membership is currently immutable in the schema;
foreign or missing principals are rejected, rather than reassigned to the owner.

## Bounded automation grants

Saving button bindings through the existing authenticated `PUT` endpoint now
requires both `devices:update` and `devices:execute`. Core resolves the source
node and issues fresh random grant IDs, storing the configurator and node beside
each binding. Incoming grant IDs are ignored when saving. Replacing even an
identical binding rotates the grant. Clearing bindings or deleting their source,
target or room revokes them through the existing binding lifecycle.

An automation ActionContext contains the grant ID and authenticated event node ID.
Current validation requires the same Space, source button/node observation and
binding, an enabled eligible configurator still holding both permissions, and the
binding's current target device/room and power action. Only `power.set` is granted.
The action path checks each target, including direct Nanoleaf targets; the queue
checks again before releasing Zigbee/Bluetooth commands. This prevents a queued
button task or command from outliving a replaced/deleted binding or revoked
configurator. Node credentials alone confer no action authority.

## HOME Voice

Voice remains a distinct integration principal. The existing authenticated,
server-created Voice ActionContext supplies satellite and dialogue session IDs.
Core checks the satellite/session/Space relationship, active unexpired session,
HOME policy and the bounded routine device capabilities at action entry, before
idempotent replay, per target and at Gateway release. Missing, closed, expired or
foreign sessions are denied. A satellite is never labelled an identified human.
Business Voice remains unavailable pending person-level identity design.

## Caller coverage

| Production path | Captured authority / required permission |
| --- | --- |
| Device command sync/async HTTP | Actual authenticated human; `devices:execute`; requested bounded capability |
| Web Action / interpreted proposal | Explicit authenticated actor through ActionContext; `devices:execute` |
| Direct Gateway pairing and power/brightness/colour | Actual authenticated human; `gateways:execute`; mapped command capability |
| Zigbee approval / Hue power-on recovery | Same authenticated approving human; `gateways:execute`; `zigbee.hue_power_on_recover` |
| Zigbee device removal | Actual authenticated human; `integrations:delete`; `zigbee.remove`; local deletion only after confirmed success |
| YouTube Gateway playback | Actual authenticated human; `integrations:create`; `youtube.play`; existing local URL validation retained |
| Zigbee button worker | Configurator-issued current binding grant and event node; bounded power capability |
| HOME Voice actions | Satellite plus active dialogue session; routine device capability; HOME-only policy |
| Bluetooth approval, discovery, heartbeat and motion observations | No queue dispatch; existing scoped node/resource predicates retained |
| Room removal | No gateway execution; existing room ownership and binding cascade retained |

## Compatibility, audit and execution limits

V42 only adds command provenance and nullable binding-grant fields/index/check.
No historical actor is reconstructed, no completed/running row or sealed audit
history is rewritten, and no existing migration is modified. Historical pending
commands are denied on claim. Historical button bindings remain readable but
inactive until an authorized user explicitly resaves them to issue grants.

Grant issuance/revocation events identify the authenticated configurator, Space,
source button and grant correlation; replacement is transactional with its audit.
Enqueue, dispatch and claim-denial
events carry original principal, resource Space and command correlation. Result
events identify the executing node and use the original correlation. Existing
conservative timeout/result mappings and node/status completion predicates remain.
No gateway wire contract or new dependency is required.

Historical human/Voice action request fingerprints remain compatible. Automation
fingerprints additionally bind the grant and source node, and authority is checked
before cached outcome lookup. A renewed grant cannot reuse a previous grant's
cached success as though that new authorization had already executed.

There is no automatic replay of uncertain running commands. Duplicate polls do
not redispatch running work; duplicate/foreign results are rejected. Any future
retry must preserve and revalidate original provenance. Revocation after release
cannot recall a physical operation already sent to an adapter. Multiple-process
device reconciliation and physical radio/audio/Voice acceptance remain separate.

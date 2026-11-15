# ADR 0082: Manage prepared devices through existing gateway identities

Status: Accepted for implementation

## Decision

Core remains the authority for devices in its existing Space. Extend gateway
identities rather than creating an installer device registry. Names and expected
availability are editable through the existing gateway permissions. Management
changes use an explicit revision, independently of heartbeats, to reject stale
administrative writes. Removal is a durable revocation, not deletion of history.
It invalidates gateway credentials and credentials of voice satellites bootstrapped
from that gateway. Pending commands fail; already delivered physical actions cannot
be recalled. Legacy independently enrolled voice satellites remain independent.

Desired task placement and observed runtime health must remain distinct. A saved
task request is not evidence of installation or readiness. Moving the authoritative
Core remains subject to the existing source-fenced restore protocol; editing device
metadata cannot move a Space or grant a second writer. Offline devices cannot be
assumed to have released a task. Prepared-agent deployment and task handoff must be
verified separately before being advertised as working distributed installation.

Schema 51 also provides explicit allowed-task policies for existing integration
and voice transports. New protocol-2 enrollments start with no task permissions;
legacy nodes retain their previous authorization until explicitly configured.
Policies gate command ingress/dispatch, event ingress, integration synchronization
and gateway-linked voice authentication. Administrative writes and command claims
serialize on the existing node row. This is authorization for existing runtimes,
not software deployment, a readiness claim, an exclusive task lease or an AI
transport. Revoking a permission does not uninstall user software or activate a
microphone. Unknown task names are rejected rather than accepted as placeholders.

## Consequences

The installer uses Core APIs and existing RBAC for maintenance. Revoked devices
remain visible in management history but disappear from active command targets.
Re-enrollment requires an explicit new enrollment; old secrets never become valid
again. No public listener or remote operating-system execution is introduced.

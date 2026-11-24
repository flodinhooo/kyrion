# ADR 0091: Bind reviewed pairing to the actual Core Space

Status: Accepted for implementation

## Decision

The transfer file's Space label is not server authority. Keep the existing
gateway enrollment, Space model and one-use code; add an optional expected Space
UUID to the prepared claim. Core must compare it to the code's existing owner
Space in the atomic consume operation. A mismatch must not consume an unused
code or create another node. Retried acknowledgements also verify the requested
Space and current tenant availability. Never use the requested UUID as authority
to select or move a Space.

Advertise space-binding protocol 1 on the existing enrollment capability endpoint.
New bound clients check it before transmitting a code, so an older server cannot
silently ignore the new optional request field. Return the actual `spaceId` with
the existing enrollment response. Its existing client parser tolerates additional
response fields; preserve the exact owner-code creation response for historical
installers whose export parser requires three fields. No new endpoint, registry,
identity, Space type or database migration is required.

Persist an explicitly expected Space before the network claim. Agent enrollment
pending format 2 adds only that UUID to the existing immutable intent. Format 1
continues to resume without a new expectation; do not silently reinterpret or
rewrite it when a different/new review supplies one. This pending-file format is
separate from installer ingress journal format 2. Preserve the original identity,
credential, runtime version and acknowledgement deadline.

The existing AgentConfig can additionally retain the actual verified Space UUID;
older configurations remain loadable. Never represent a legacy response without
that field as a confirmed Space binding. Installer packet import passes its
reviewed expected UUID through both foreground and service enrollment; export
requires compatible Core before issuing a fresh code. Existing unbound clients,
legacy registrations and deployed configuration remain compatible.

## Verification

Test real PostgreSQL code consumption, mismatched/unavailable Spaces, replay,
immutable pending expectations, old capability refusal before any claim,
malformed/mismatched server responses and same-node lost acknowledgement.
Exercise actual Windows protected storage and actual target identity separately
from protocol doubles. These changes do not complete Windows health/runtime,
SCM deployment, task placement or exclusive cross-device migration.

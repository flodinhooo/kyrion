# ADR 0084: Package the existing prepared agent with the downloaded installer

Status: Accepted for implementation

## Decision

The native installer embeds the existing `services/gateway-agent` Python modules
using an explicit public-source allowlist. The source archive and native/service
builders seal these same inputs and include their hashes in build metadata.
There is no copied agent source tree, dynamic plug-in discovery, downloaded Python
dependency or second enrollment identity. The embedded interpreter in the frozen
installer can execute this standard-library agent without user-installed Python.

Source resolution may reach the existing component only from the actual installer
source root and only for the enumerated module names. Compilation uses immutable
staged copies. Secret files, tests, caches and arbitrary sibling paths are excluded.

Prepared enrollment continues to use the existing protected pending state,
short-lived Core code, TLS pin and stable gateway identity. Running an embedded
agent is distinct from installing its operating-system service. Windows prepared
storage, dedicated service ownership, restart recovery and explicit task placement
must be implemented and tested before full node installation can be claimed.

Foreground installer review passes the displayed certificate digest into the
existing enrollment operation. That digest is checked against the exact bytes
before private trust and pending secrets are published. A later source-file
change cannot substitute a different certificate after the user's confirmation.

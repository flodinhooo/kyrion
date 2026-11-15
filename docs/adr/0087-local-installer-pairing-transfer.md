# ADR 0087: Local installer pairing transfer through existing Core enrollment

Status: Accepted for implementation

## Decision

The authorized local installer exports a short-lived one-use pairing transfer
using the existing Core gateway-enrollment API, current linked identity and Space
permissions. This is not a new account/device registry or remote installation.
The other target must run its own installer. Export requires explicit intent,
protected local storage and a real pinned-TLS check of the configured agent
ingress before issuing an enrollment. Never print the enrollment secret.

A bounded versioned JSON file carries the Core HTTPS origin, public certificate,
certificate SHA-256, Core enrollment identifier/expiry and one-use enrollment
secret. It contains no owner session, web password or long-lived node credential.
The file is a bearer capability until expiry: protect it, transfer privately and
compare the certificate fingerprint displayed by the originating installer with
the target review. It is not an independently signed public release artifact.
No automatic upload or LAN-wide disclosure is allowed.

The target reviews immutable in-memory parsed input before materializing temporary
private enrollment files. Reuse the existing prepared enrollment and service
journals, including same-input retry and code expiry checks. Existing final node
identities are never replaced by importing another transfer. Existing pending
enrollment remains authoritative after interruption; import does not renew an
expired code or manufacture a successful connection.

Use only the installation's configured HTTPS hostname/port, whose certificate and
proxy virtual host already agree. Do not emit unconfigured IP-host alternatives.
Origin-side connection success does not prove DNS/reachability from another
device; the target performs its own pinned local-only connection. Unsupported
existing ingress must be explicitly extended and tested before export, never
silently rewritten as part of issuing a code.

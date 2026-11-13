# ADR 0059: Authenticated resumable update staging

Status: Accepted

## Decision

The installed update workflow rechecks the existing signed release index before
downloading. Its authenticated manifest digest binds the exact runtime manifest;
platform, release and compatibility must also match the candidate. Runtime
archives remain subject to the existing bundle validators, exact file checks and
Linux image identity checks. No new release or integration authority is created.

The owner reviews artifact sizes before large downloads. HTTPS uses normal
certificate verification, no redirects, no ambient proxies or credentials.
Artifacts are streamed into private owned staging files with an expected size
and SHA-256. A bounded HTTP Range response may continue an interrupted file;
an ignored Range restarts the same owned partial file. Only a complete verified
file is published, without overwriting an existing entry. Invalid bytes never
become executable state. The signed index proof and public trust snapshot are
preserved alongside the manifest for subsequent revalidation.

Staging holds the installation lock and does not stop services, mutate databases
or claim installation success. Download verification is an explicit intermediate
state of the still-open update transaction coordinator. A rotated or changed
policy requires fresh authorization. Old staging data is preserved rather than
silently merged into another release.

HTTP response handling follows [RFC 9110 range semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-range).
Tests must distinguish injected transports from actual local HTTPS; neither is a
public release or a complete update/rollback acceptance test.

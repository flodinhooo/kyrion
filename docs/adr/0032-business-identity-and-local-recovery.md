# ADR 0032: Business identity proof and host-local recovery

Status: Accepted for Spaces Milestone 02. Multi-Space runtime remains disabled.

Email control, DNS domain control and local administrative attestation are three
different proofs. SMTP challenges prove mailbox access; DNS TXT challenges prove
control of a domain at verification time. Local attestation is labelled separately
and cannot satisfy strict Business policy. No existing identity is auto-verified.

Strict policy requires current DNS proofs, verified email for every enabled member,
and provisioned local recovery. Activation explicitly invalidates outstanding
invitations. Expired DNS proof blocks new enrollment/email changes, not existing
members or OWNER access. Policy changes cannot exclude enabled members. Exact
domain matches are used; subdomains must be listed and verified independently.

Email changes keep the existing verified address until a distinct pending address
is proved. Resending supersedes pending proofs. Registration proofs bind an email
to an invitation and Space; creating an account and consuming both proofs commit
together. Tokens are random, hashed, expiring and one-use. SMTP is optional, uses
TLS and never returns verification credentials to Web clients or normal logs.

Recovery is an interactive host-local CLI, not an HTTP endpoint. It requires the
installation database and audit key, a protected per-Space host key and a separate
offline recovery code. Provisioning additionally requires the current OWNER
password. Opening consumes the code and issues a five-minute one-use recovery
session bound to the existing OWNER, Space and installation. Completion rotates
the password and offline code, revokes sessions and preserves roles/membership.
No recovery path creates accounts or OWNER grants. Failed proof is audited without
credentials. The CLI does not start Spring, workers, HTTP or external providers.

V38 adds identity/proof/policy/recovery data only. The committed Spaces V37 is not
renumbered: parallel main-worktree V37 calendar-context work is an explicit
integration collision which must be resolved before deployment. Knowledge/RAG
work is absent from this branch and is not copied from another agent's worktree.

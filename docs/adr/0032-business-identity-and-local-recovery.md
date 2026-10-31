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

The feature branch originally assigned V38 to identity/proof/policy/recovery and
V37 to Spaces. For the combined source, [ADR 0033](0033-combined-development-migration-history.md)
supersedes that numbering: V38 is Spaces, V39 is identity/recovery. SQL contents
are preserved, and the inspected live database has neither applied. Already
applied feature histories remain validation-blocked pending a reviewed plan.

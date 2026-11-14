# ADR 0078: Default Windows installation uses the protected application folder

Status: Accepted for implementation, 2026-11-14.

Actual read-only testing exposed that the default ProgramData ancestor grants
Users create/write rights rejected by the existing installer ancestor policy.
Choosing it as the default installation or crypto parent made the regular native
path fail before elevation. Preserve that policy and choose an appropriate
OS-resolved ProgramFiles location for the existing single private installation
root, including its explicitly ACL-scoped service data directories.

Resolve ProgramFiles through SHGetKnownFolderPath, never a caller environment
alias. Default new installations to ProgramFiles/Kyrion. Explicit existing targets
continue through their normal ownership checks; this change performs no migration.
The established per-directory service identities, backup/update journals and
software-versus-data removal choices continue to govern this root.

GnuPG's exclusive temporary agent directories use the short protected system
application folder as their parent, validated before password handoff. Their
private descriptor, exclusive creation and scoped cleanup are required. No global
Windows ACL is modified. Redirected paths beyond the checked socket-length bound
are unsupported for this crypto operation and fail explicitly. Whole-host and
pre-login service acceptance still require the isolated elevated Windows test.

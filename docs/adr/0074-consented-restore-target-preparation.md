# ADR 0074: Reuse signed acquisition and package preparation for fresh restores

Status: Accepted for implementation, 2026-11-14.

Restore on an empty supported target reuses the build-bound signed release
channel and platform runtime provisioning. It does not introduce another backup,
release or installation identity. Download consent precedes large artifacts;
restore consent precedes OS/service preparation. Manual independently trusted
bundles remain supported. Existing supported schema/API restrictions still apply.

Before Debian package mutation, persist the existing authority restore fence with
the exact encrypted-backup SHA-256. Prerequisite operations may cross that fence
only with the same explicitly supplied restore request. They must still reject
retired authority and update fences. Ordinary install, crypto maintenance, startup
and application activation stay blocked. Interruption resumes the same private
journal, manifest, target configuration, backup binding and approved package plan.

This preparation does not authorize data replacement or remove the source
retirement receipt requirement. An unrecognized existing target, changed request,
unsigned/incompatible release or failed real runtime check stops the flow.
Unknown-source and same-root disaster recovery remain separate missing work.

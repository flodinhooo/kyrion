# ADR 0026: Local development service recovery

- Status: Accepted
- Date: 2026-10-22

## Context

Core authentication cannot authorise its own cold start. The Windows development
stack needs an explicit operator recovery path when only Web is available.
ADR 0016 intentionally gives Web no host lifecycle authority.

## Decision

A separately launched, loopback-only development recovery helper accepts only
`start` and `restart` for a fixed service list. A random operator key is held in
an ignored local file and entered explicitly in Web; it is never embedded in
Web configuration or returned by an API. Web only forwards bounded requests.
The helper records correlation IDs and outcomes before and after execution.
This is host operator authority, separate from platform accounts, and grants
no device, account or business-operation permission. Core remains authoritative
for all ordinary application actions. Recovery must work without its database.

The initial implementation manages PostgreSQL, Core, AI and Ollama on Windows,
plus Parakeet and Chatterbox in the existing WSL distribution. An operator-configured Pi
host additionally allows only three fixed user systemd units: Spotify receiver,
Voice Satellite and media player, through the existing pinned SSH identity.
Restart stops only Windows processes previously launched by the helper;
existing external processes, PostgreSQL and running WSL speech services are
preserved. Live testing found that even targeted Linux speech-process SIGTERM
could interrupt WSL and Docker on this host. WSL lifecycle restart is therefore
excluded rather than offered as safe. Missing WSL speech services can still start.
The WSL host and its Windows process tree are never terminated by the helper.
Web stays running to show results.
Production deployment and privileged Pi services are outside this allowlist.
No Docker socket, SSH key, host or executable path is accepted from browser input.

## Consequences

The October 30 CLI extension can narrow a restart to one of the same fixed
Windows targets (`core`, `ai`, `ollama`). Only processes owned by that helper may
be restarted; external processes, WSL and untargeted/Pi services are preserved.
The CLI's explicit PostgreSQL restart preserves its existing container/data and
waits for SQL readiness and Core reconnect. It does not grant Web additional
database or process authority, and does not permit global WSL/host lifecycle operations.

Windows Web's `predev` launcher ensures the helper is running; it can also be
started independently. Its key is a
host administration credential and is not a Kyrion account recovery mechanism.
Local JSONL recovery evidence is separate from the Core activity log. It is not
claimed to have Core audit integrity. Production lifecycle management needs a
separate reviewed design and is not enabled by this development feature.

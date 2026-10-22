# Windows local service recovery acceptance

Implemented a development-only recovery page linked from Login and System
services, a same-origin loopback Web proxy, and an independent host helper.
Windows `pnpm dev` ensures the helper is running. Host execution remains outside
Web, protected by a separately entered random operator key and a fixed allowlist.
See [ADR 0026](../adr/0026-local-development-service-recovery.md) and
[startup instructions](../development-startup.md).

## Verified behavior

- Recovery remained accessible and accepted startup while Core and AI were down.
- A full start completed for PostgreSQL, Core, AI, Ollama, STT, Chatterbox TTS,
  and the configured Pi Spotify receiver, Voice Satellite and media player.
- A real headless Chromium session verified German/English presentation,
  operator-key entry, status display and a restart accepted after exactly one
  browser confirmation. The final restart completed for managed Core/AI and the
  three Pi user services, preserving running WSL speech services and PostgreSQL.
- Subsequent probes: Web HTTP 200, Core `UP`, AI/STT `ok`, TTS `ready`, Ollama
  version validated, and PostgreSQL `SELECT 1` returned `1`. The database container
  start timestamp was unchanged by the final restart. All three Pi user units
  and the gateway agent reported `active` over pinned-key SSH.
- Live proxy requests returned 200 for a valid status request, 401 for a wrong
  operator key, and 403 for a cross-origin request.
- 108 Web tests, four Node policy tests, TypeScript, ESLint, production Web
  build, Node syntax checks and `git diff --check` passed. The Web build used
  `.next-review` separately from the running development server.

The final successful start correlation was
`7ae3ed7e-860f-4b3f-8f37-3b6ef2412ae1`; the confirmed restart was
`ea56f234-8fdc-4810-b757-3a7cb0838c7d`. Recovery audit and logs are ignored local
artifacts below `.run/dev-recovery/`, separate from Core's activity log.

## Existing installation and intentional limits

The installed database is V33. The primary checkout has V31 with a checksum that
does not match the installed history. Its freshly built JAR was therefore not
used for final operation. Local operator settings select the existing matching
artifact from `.worktrees/calendar-ha-recovery`, with an immutable runtime copy
and the main checkout's existing configuration. Database history, checksums,
secrets and the recovery worktree's user changes were not rewritten.

Live speech-runtime termination, including targeted Linux SIGTERM, repeatedly
interrupted WSL/Docker on this host. The final helper therefore never terminates
WSL speech processes or WSL itself. It can start missing STT/TTS processes and
preserves running ones during restart. A policy regression test enforces this.
The affected services were restored before final verification. Resolving the
host's WSL termination behavior remains separate work.

The final restart does not restart Web, PostgreSQL, externally launched Windows
processes, running WSL speech processes or privileged Pi services. Production
hosting lifecycle is not implemented. Cold TTS startup took several minutes.
Spotify receiver readiness is confirmed; phone discovery, audible playback and
end-to-end voice acceptance were not physically verified.

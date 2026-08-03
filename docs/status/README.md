# Kyrion Development Status

Last updated: 2026-08-03

This directory is the durable handoff point for continuing development in a
new chat or work session. Read this file together with the root `AGENTS.md`,
`README.md` and the relevant architecture documents before changing code.

## Current vertical slices

The local text and voice path is implemented:

```text
Browser on http://localhost:3000
    |
    v
Next.js POST /api/chat
    |
    v
Kyrion AI Service on http://127.0.0.1:8000
    |
    v
Ollama on http://127.0.0.1:11434
    |
    v
Configured local model
```

The first trusted Core persistence path is also implemented:

```text
Browser /activity
    |
    v
Next.js GET /api/activity
    |
    v
Kyrion Core GET /v1/activity
    |
    v
PostgreSQL on E:\Kyrion\Data\postgres
```

## Completed

### Project and architecture

- Monorepo structure for web, mobile, Core, AI and shared contracts.
- Product vision, principles, architecture and roadmap documentation.
- Root `AGENTS.md` with repository-wide quality and architecture rules.
- Marketplace, plugin and enterprise vision.
- Kotlin and Spring Boot Core foundation with a PostgreSQL-backed, append-only
  activity event log.
- Core-owned `GET /v1/activity` contract with data-minimised events and
  correlation identifiers.
- Flyway-managed database schema and an architecture decision record for the
  persistence boundary.
- Identity and server-side session persistence schema prepared in Flyway V2.
- Argon2id password hashing and opaque 256-bit session-token generation.
- Only SHA-256 session-token hashes are designed to be stored; raw session
  tokens are returned once for the future protected cookie.
- Tested session lifecycle domain logic for creation, seven-day expiry,
  last-seen updates, authentication and revocation.
- One-time local-owner setup, login, current-user and logout HTTP contracts.
- Same-origin `HttpOnly`, `SameSite=Strict` session cookie and double-submit
  CSRF protection at the Next.js boundary.
- Authoritative protection for workspace pages, private Next.js APIs and Core
  activity/conversation resources.
- Owner-scoped PostgreSQL conversations and ordered messages through Flyway V3.
- AI actions remain proposals; future device actions must pass through Core.

### Web application

- Next.js 16, React 19, TypeScript and Tailwind CSS foundation.
- Persistent shared application shell using a workspace route group.
- Responsive sidebar and accessible mobile shadcn Sheet.
- Chat, Home, Automations, Knowledge and Settings routes.
- German and English UI resources.
- Persistent light/dark theme selection.
- White/gold light theme and cyan/royal-blue dark theme.
- Provider-neutral typed chat contracts.
- Streaming chat UI with cancellation and translated errors.
- Markdown rendering, intelligent autoscroll and refined stream states.
- One validated conversation identifier per mounted chat session.
- Live AI-service readiness and configured-model status.
- Dedicated local-model page with validated Ollama metadata and per-device
  selection.
- Initial conversational Voice Mode opened from the Velora orb, using browser
  speech recognition and system speech synthesis as transparent prototype
  providers.
- Sentence-based streaming speech: completed sentences begin playing while the
  model continues generating later sentences.
- Voice turns are isolated by assistant message ID so prior conversation text
  and cancelled browser utterances cannot enter a new response queue.
- Centred Voice Mode layout with a wider transcript, automatic spoken-word
  tracking and a subtle animated focus outline.
- Dedicated voice settings with per-language browser voice selection, previews,
  local/online labels and a persisted speaking rate.
- Primary Activity navigation backed by persisted Core events, including clear
  loading, unavailable and empty states.
- Runtime validation of Core responses in the Next.js server-side proxy.
- Next.js server-side `/api/chat` proxy; Ollama is never called directly by the
  browser.

### AI service

- Python 3.12 project using FastAPI, Pydantic, HTTPX and Uvicorn.
- Provider-neutral `LanguageModelProvider` protocol.
- Ollama provider using `/api/chat` with NDJSON streaming.
- Reasoning-capable models use visible answer streaming without an invisible
  thinking pass; models remain warm for ten minutes and use a 4096-token
  runtime context for normal chat.
- Stable Kyrion chat events and error codes.
- Modular Kyrion-owned Velora system prompt with local-first and safety rules.
- Request validation, health endpoint and tests.
- Local virtual environment at `services/ai/.venv` (ignored by Git).

### Local runtime

- PostgreSQL 17 development container bound only to localhost.
- PostgreSQL files stored through a bind mount at
  `E:\Kyrion\Data\postgres`, not an anonymous Docker volume on C:.

- Ollama 0.32.5 installed at `E:\Ollama\App`.
- Physical model storage at `E:\Ollama\Models`.
- `C:\Users\Flo\.ollama\models` is an NTFS junction to the E: model directory
  because this Ollama Windows build continued to resolve its default path.
- Installed and verified models:
  - `gemma3:4b` (default Kyrion model);
  - `qwen3:8b` (alternative model).
- Both models load fully on the NVIDIA RTX 2070 8 GB using 100% GPU execution
  at a 4096-token context during the smoke test.

## Verification completed

- `pnpm lint`: passed.
- `pnpm build`: passed, including the dynamic chat and model benchmark routes.
- Python Ruff checks: passed.
- Python tests: 31 passed.
- Kotlin Core tests and boot JAR build: passed.
- Flyway migrations V1 through V3, Core health and persisted startup events: passed
  against PostgreSQL.
- Password hashing, session-token hashing and session lifecycle tests: passed.
- Isolated PostgreSQL 17 integration tests for one-time setup, HTTP auth
  contracts, password rotation and conversation owner isolation: passed.
- Web authentication policy tests for `HttpOnly`, `SameSite`, `Secure` and CSRF
  token matching: passed.
- Web `/api/activity` end-to-end response: passed.
- Warm `qwen3:8b` smoke test produced its first visible token in about 0.52
  seconds and completed a short response in about 0.63 seconds on the current
  machine; this is an observation, not a performance guarantee.
- Ollama API health: passed.
- `gemma3:4b` inference: passed.
- `qwen3:8b` inference: passed.

## Current limitations

- A conversation remains transient until a response produces visible assistant
  content; completed and partially stopped visible transcripts are then
  persisted per owner.
- There is no context compaction, deletion or retention pipeline yet.
- No owner has been created on the current development installation yet; the
  one-time setup screen is ready at `/login`.
- Core currently implements activity, local authentication and conversation
  persistence; command execution and integration capabilities remain planned.
- Activity actor ownership, retention and tamper-evidence are not implemented.
- Available models remain deployment-controlled through `KYRION_ALLOWED_MODELS`;
  each browser can select one locally for its chat requests.
- Model benchmark results currently live only in page state and are discarded
  when the model page is left or reloaded.
- Voice Mode currently depends on browser speech APIs. Speech recognition may
  use an external browser service and is not yet Kyrion's planned local voice
  pipeline.
- Voice interruption while Velora is actively speaking is not yet a complete
  hands-free barge-in flow because continuous recognition could hear the
  assistant's own browser speech.
- Home, Automations and Knowledge are intentional placeholders.

## Recommended next step

Complete the live owner flow and harden the implemented slices:

1. create the real local owner through `/login` and verify login/logout;
2. send a chat turn, reload it from the sidebar and verify persistence;
3. add integration tests proving cookie flags, expiry, revocation and endpoint
   ownership;
4. add login throttling before any remote exposure;
5. add conversation deletion, retention and context compaction.

Do not expose the prepared session repository directly and do not store tokens
in browser local storage. Continue with one verified vertical slice at a time.

## How to resume

In a new agent chat, use this prompt:

> Read `AGENTS.md`, `README.md`, all project-owned files in `docs/`, especially
> `docs/status/README.md`, `docs/status/TODO.md` and both ADRs. Inspect the
> current implementation and uncommitted changes. Continue with the one-time
> local-owner setup and authenticated session vertical slice. Preserve Core as
> the authentication authority and do not store credentials or tokens in
> browser local storage.

For runtime commands, see [Local Development Startup](../development-startup.md).

The concrete next-session tasks are tracked in [TODO.md](TODO.md).

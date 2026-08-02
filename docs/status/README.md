# Kyrion Development Status

Last updated: 2026-08-02

This directory is the durable handoff point for continuing development in a
new chat or work session. Read this file together with the root `AGENTS.md`,
`README.md` and the relevant architecture documents before changing code.

## Current vertical slice

The first real text-chat path is implemented:

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
- Python tests: 30 passed.
- Kotlin Core tests and boot JAR build: passed.
- Flyway migration, Core health and persisted startup event: passed against
  PostgreSQL.
- Web `/api/activity` end-to-end response: passed.
- Ollama API health: passed.
- `gemma3:4b` inference: passed.
- `qwen3:8b` inference: passed.

## Current limitations

- Conversations exist only in React state and disappear when the chat page is
  unmounted or the browser is refreshed.
- There is no conversation history or summarisation pipeline yet; the current
  database stores only Core activity events.
- There is no login or user model yet.
- Core currently implements only the first activity vertical slice; it has no
  authentication, command execution or integration capabilities yet.
- Activity actor ownership, retention and tamper-evidence are not implemented.
- Available models remain deployment-controlled through `KYRION_ALLOWED_MODELS`;
  each browser can select one locally for its chat requests.
- Model benchmark results currently live only in page state and are discarded
  when the model page is left or reloaded.
- Voice Mode currently depends on browser speech APIs. Speech recognition may
  use an external browser service and is not yet Kyrion's planned local voice
  pipeline.
- Home, Automations and Knowledge are intentional placeholders.

## Recommended next step

Define the Core/database boundary for conversation persistence:

1. assign conversation ownership across Web, Core and AI;
2. define the minimum conversation and message contracts;
3. record the persistence decision before introducing PostgreSQL;
4. keep voice interaction as a separate input/output layer that can reuse the
   same conversation and capability contracts later.

Do not introduce login, PostgreSQL, containers and the mobile application in a
single change. Continue with one verified vertical slice at a time.

## How to resume

In a new agent chat, use this prompt:

> Read `AGENTS.md`, `README.md`, all project-owned files in `docs/`, and inspect
> the current implementation. Start from `docs/status/README.md` and continue
> the recommended next step without changing Kyrion's architecture boundaries.

For runtime commands, see [Local Development Startup](../development-startup.md).

The concrete next-session tasks are tracked in [TODO.md](TODO.md).

# Kyrion Development Status

Last updated: 2026-08-01

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
- Core remains planned as Kotlin and Spring Boot.
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
- Next.js server-side `/api/chat` proxy; Ollama is never called directly by the
  browser.

### AI service

- Python 3.12 project using FastAPI, Pydantic, HTTPX and Uvicorn.
- Provider-neutral `LanguageModelProvider` protocol.
- Ollama provider using `/api/chat` with NDJSON streaming.
- Stable Kyrion chat events and error codes.
- Request validation, health endpoint and tests.
- Local virtual environment at `services/ai/.venv` (ignored by Git).

### Local runtime

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
- `pnpm build`: passed, including the dynamic `/api/chat` route.
- Python Ruff checks: passed.
- Python tests: 3 passed.
- Ollama API health: passed.
- `gemma3:4b` inference: passed.
- `qwen3:8b` inference: passed.

## Current limitations

- Conversations exist only in React state and disappear when the chat page is
  unmounted or the browser is refreshed.
- There is no database, conversation history or summarisation pipeline yet.
- There is no login or user model yet.
- There is no Kotlin Core implementation yet.
- AI responses are not yet governed by a Kyrion system prompt.
- Model selection is configured through `OLLAMA_MODEL`; it is not yet exposed
  in Settings.
- Home, Automations, Knowledge and Settings are intentional placeholders.

## Recommended next step

Complete and refine the Ollama chat vertical slice before adding persistence:

1. test real conversations through `http://localhost:3000`;
2. improve response rendering, autoscroll and input keyboard behaviour;
3. add AI-service readiness to the web status indicator;
4. add a controlled model selector or keep the model deployment-configured;
5. introduce conversation identifiers and decide the Core/database boundary;
6. then add PostgreSQL-backed conversation history and context compaction.

Do not add authentication, PostgreSQL and Kotlin Core simultaneously. Continue
with one verified vertical slice at a time.

## How to resume

In a new agent chat, use this prompt:

> Read `AGENTS.md`, `README.md`, all project-owned files in `docs/`, and inspect
> the current implementation. Start from `docs/status/README.md` and continue
> the recommended next step without changing Kyrion's architecture boundaries.

For runtime commands, see [Local Development Startup](../development-startup.md).

The concrete next-session tasks are tracked in [TODO.md](TODO.md).

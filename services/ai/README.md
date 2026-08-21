# Kyrion AI Service

The AI service owns provider-specific model communication. The web application
and Kyrion Core communicate only through Kyrion's provider-neutral chat events.

## Local setup

1. Install and start Ollama.
2. Pull the configured model, for example `ollama pull gemma3:4b`.
3. Copy `.env.example` to `.env` or provide the variables through the shell.
4. Create a virtual environment and install the project with development tools.
5. Start the service with
   `uvicorn kyrion_ai.app:app --reload --port 8000 --env-file .env`.

STT is selected independently with `KYRION_STT_PROVIDER`. The productive
development profile and default use `http_openai` and a local NeMo-Speech.cpp server so
the AI boundary stays independent of NVIDIA Parakeet. `faster_whisper` remains
an explicit compatibility option; there is no silent fallback between STT
engines.

The local Ollama API requires no authentication and listens on
`http://127.0.0.1:11434` by default. Do not expose it directly to the internet.

## Endpoints

- `GET /health`: service and provider configuration status;
- `POST /v1/chat/stream`: provider-neutral NDJSON chat event stream.

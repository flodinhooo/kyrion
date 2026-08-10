# Local Development Startup

This guide starts the complete local Kyrion stack on Windows.

## Installed locations

- Ollama application: `E:\Ollama\App\ollama.exe`
- Ollama models: `E:\Ollama\Models`
- Kyrion repository: `E:\dev\Kyrion\kyrion`
- AI virtual environment: `services\ai\.venv`

## Start the complete stack

Open four PowerShell windows. Docker Desktop must also be running.

### 1. Start PostgreSQL

Create `infrastructure\.env` from `infrastructure\.env.example`, choose a
local development password and keep the default data path on E:. Then run:

```powershell
Set-Location 'E:\dev\Kyrion\kyrion'
docker compose -f infrastructure\compose.yml up -d postgres
docker compose -f infrastructure\compose.yml ps
```

The database uses a bind mount at `E:\Kyrion\Data\postgres` by default. This
is an ordinary E: directory, not an anonymous Docker volume on C:.

### 2. Start Kyrion Core

Use the same password selected in `infrastructure\.env`:

```powershell
Set-Location 'E:\dev\Kyrion\kyrion\services\core'
$env:KYRION_DATABASE_PASSWORD = 'your-local-database-password'
.\gradlew.bat bootRun
```

Leave this window open. Verify Core at
`http://127.0.0.1:8080/actuator/health`. Recent persisted events are available
at `http://127.0.0.1:8080/v1/activity`.

### 3. Start Ollama

```powershell
& 'E:\Ollama\App\ollama.exe' serve
```

Leave this window open. The API should become available at
`http://127.0.0.1:11434`.

Verify it in another PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version
& 'E:\Ollama\App\ollama.exe' list
```

### 4. Start the Kyrion AI service

```powershell
Set-Location 'E:\dev\Kyrion\kyrion\services\ai'
& '.\.venv\Scripts\python.exe' -m uvicorn kyrion_ai.app:app --reload --host 127.0.0.1 --port 8000
```

Leave this window open. Verify it at `http://127.0.0.1:8000/health`.

The default model is `gemma3:4b`. To test Qwen for one PowerShell session:

```powershell
$env:OLLAMA_MODEL = 'qwen3:8b'
& '.\.venv\Scripts\python.exe' -m uvicorn kyrion_ai.app:app --reload --host 127.0.0.1 --port 8000
```

The environment variable must be set before starting the AI service.

### Experimental XTTS-v2 voice test (opt-in)

XTTS-v2 is an experimental MVP provider. Chatterbox on port 8020 must remain
running because it is the automatic batch fallback. Start the isolated XTTS
runtime in the `Kyrion-Voice-Training` WSL environment:

```bash
cd /mnt/e/dev/Kyrion/kyrion
python services/ai/runtime/xtts_v2_streaming_tts_server.py --host 0.0.0.0 --port 8031
```

Then opt in before starting the AI service:

```powershell
$env:KYRION_TTS_PROVIDER = 'xtts'
$env:KYRION_XTTS_EXPERIMENTAL_ENABLED = 'true'
$env:KYRION_XTTS_TTS_URL = 'http://127.0.0.1:8031'
& '.\.venv\Scripts\python.exe' -m uvicorn kyrion_ai.app:app --host 127.0.0.1 --port 8000
```

Without both provider selection and the feature flag, XTTS cannot run. The
runtime uses 20-token chunks. It does not run Faster-Whisper. Its private
`max_gen_mel_tokens` length cap is enabled by default only inside this runtime
as an unstable MVP workaround; set
`KYRION_XTTS_UNSTABLE_LENGTH_CAP_ENABLED=false` to disable it for diagnostics.
The AI service buffers and validates the experimental stream before returning
the WAV, so a crash, timeout, malformed stream or suspicious duration can fall
back cleanly without releasing partial XTTS audio.

### 5. Start Kyrion Web

```powershell
Set-Location 'E:\dev\Kyrion\kyrion\apps\web'
pnpm dev
```

Open `http://localhost:3000` and send a chat message.

## Request flow

The browser calls only Next.js. Next.js reads trusted activity through Kyrion
Core using `CORE_SERVICE_URL`, which defaults to `http://127.0.0.1:8080`, and
forwards chat requests to the AI service using `AI_SERVICE_URL`, which defaults
to `http://127.0.0.1:8000`. The AI service then calls Ollama using
`OLLAMA_BASE_URL`, which defaults to `http://127.0.0.1:11434`.

Configuration examples are stored in:

- `apps/web/.env.example`;
- `services/ai/.env.example`;
- `infrastructure/.env.example`.

## Stop the stack

Press `Ctrl+C` in the Web, Core and AI PowerShell windows. Press `Ctrl+C` in
the Ollama server window if it was started manually. Stop PostgreSQL with:

```powershell
docker compose -f infrastructure\compose.yml stop postgres
```

Stopping the container does not remove the data stored on E:.

## Troubleshooting

### The web page says the local model is unavailable

Check all four endpoints in order:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8080/actuator/health
Invoke-WebRequest http://localhost:3000
```

### Core cannot connect to PostgreSQL

Confirm that PostgreSQL is healthy and that Core uses the same password as
`infrastructure\.env`:

```powershell
docker compose -f infrastructure\compose.yml ps
$env:KYRION_DATABASE_PASSWORD = 'the-same-local-password'
```

Flyway currently applies the activity-log schema (V1) and the prepared identity
and session schema (V2). No login user is created automatically.

### A model is missing

```powershell
& 'E:\Ollama\App\ollama.exe' list
& 'E:\Ollama\App\ollama.exe' pull gemma3:4b
& 'E:\Ollama\App\ollama.exe' pull qwen3:8b
```

### C: starts filling again

Confirm that the default model directory remains a junction to E:

```powershell
Get-Item "$env:USERPROFILE\.ollama\models" -Force |
  Select-Object FullName, LinkType, Target
```

It should report `Junction` and the target `E:\Ollama\Models`.

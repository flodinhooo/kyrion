# Local Development Startup

This guide starts the complete local Kyrion text-chat stack on Windows.

## Installed locations

- Ollama application: `E:\Ollama\App\ollama.exe`
- Ollama models: `E:\Ollama\Models`
- Kyrion repository: `E:\dev\Kyrion\kyrion`
- AI virtual environment: `services\ai\.venv`

## Start the complete stack

Open three PowerShell windows.

### 1. Start Ollama

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

### 2. Start the Kyrion AI service

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

### 3. Start Kyrion Web

```powershell
Set-Location 'E:\dev\Kyrion\kyrion\apps\web'
pnpm dev
```

Open `http://localhost:3000` and send a chat message.

## Request flow

The browser calls only Next.js. Next.js forwards chat requests to the AI
service using `AI_SERVICE_URL`, which defaults to `http://127.0.0.1:8000`. The
AI service then calls Ollama using `OLLAMA_BASE_URL`, which defaults to
`http://127.0.0.1:11434`.

Configuration examples are stored in:

- `apps/web/.env.example`;
- `services/ai/.env.example`.

## Stop the stack

Press `Ctrl+C` in the Web and AI PowerShell windows. Press `Ctrl+C` in the
Ollama server window if it was started manually.

## Troubleshooting

### The web page says the local model is unavailable

Check all three endpoints in order:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-WebRequest http://localhost:3000
```

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

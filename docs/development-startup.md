# Local Development Startup

This guide starts the complete local Kyrion stack on Windows.
For isolated worktrees and verified configuration loading, use the
[Windows worktree workflow](windows-development.md).

## Single-command Windows development startup

Latest Google acceptance and the approval-gated Pi/Core LAN repair are recorded
in [Sprint 03](status/2026-10-30-stabilization-sprint-03.md) and the
[Pi/Core and Voice procedure](pi-core-and-voice-acceptance.md).

For the current live acceptance, diagnostics, scoped restart boundaries and
October 31 demonstration, see the [demo checklist](demo-readiness-2026-10-31.md)
and [Sprint 02 evidence](status/2026-10-30-stabilization-sprint-02.md).

With Docker Desktop running and the existing local configuration/dependencies
available, run from the repository root:

```powershell
node infrastructure/dev-stack.mjs start
node infrastructure/dev-stack.mjs status
node infrastructure/dev-stack.mjs logs tts
```

The CLI reuses the existing operator-key protected recovery helper. It starts
Web independently, waits for PostgreSQL SQL readiness before Core, allows ten
minutes for database recovery and fifteen minutes for TTS, and verifies actual
HTTP health responses. It preserves running services. `status` / `health` return
a nonzero exit code if any required local service is unavailable. Logs remain
local below `.run/dev-recovery/`. The configured optional Pi units use the
existing pinned SSH connection. No credentials are printed by status/start.

`node infrastructure/dev-stack.mjs restart --confirm` uses the helper's existing
bounded restart policy: only its managed Windows processes and configured Pi
user units restart. PostgreSQL, Web, external processes and running WSL speech
services remain running. It is not a full-machine restart or a per-service
restart. For foreground processes, use Ctrl+C in their owning terminals. Stop
PostgreSQL only after stopping Core with
`docker compose -f infrastructure/compose.yml stop postgres`; never use `down -v`.

The helper reads local artifact settings at launch. The stabilization acceptance
selects a tested JAR built from the primary checkout, after comparing all 33
installed Flyway checksums; the recovery worktree is no longer required for the
next helper launch. Rebuild and select a matching artifact after Core changes.
An already-running helper retains its previous settings until its next launch.

Chatterbox uses the existing persistent WSL Hugging Face cache in offline mode;
model provisioning is separate from startup. The selected Velora reference is
preserved. The updated runtime exposes `/live` (HTTP process), `/ready` (503
during loading/failure, 200 after warmup) and backward-compatible `/health`
with initialization stage and a bounded error code. Transient local I/O failures
retry twice with backoff; permanent configuration errors remain visible without
a restart loop. `KYRION_CHATTERBOX_MODEL_DIRECTORY` and
`KYRION_CHATTERBOX_REFERENCE` optionally select existing local files;
`KYRION_CHATTERBOX_DEVICE=cpu` is an explicit diagnostic option, with CUDA still
the default. Running speech processes are preserved; new runtime code becomes
active on their next safe start. No provider/voice switch is performed.

The manual startup steps below remain available for individual services.

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

Configure the local Core values in `infrastructure\.env` using
`infrastructure\.env.example`. Core loads that repository-wide file through
Spring Boot's optional import when started from `services\core`. The real
`.env` is ignored by Git. Process/system environment variables take precedence
over values in that file, followed by the defaults in `application.yml`.

Core uses `KYRION_POSTGRES_DB`, `KYRION_POSTGRES_USER` and
`KYRION_POSTGRES_PASSWORD` from `infrastructure\.env` directly. Explicit
`KYRION_DATABASE_*` process variables remain supported and take precedence.
Start Core without repeating variables in every shell:

```powershell
Set-Location 'E:\dev\Kyrion\kyrion\services\core'
.\gradlew.bat bootRun
```

Leave this window open. Verify Core at
`http://127.0.0.1:8080/actuator/health`. Recent persisted events are available
at `http://127.0.0.1:8080/v1/activity`.

The LAN bind is required for the authenticated gateway and Voice Satellite.
The development router publishes the Core host as `kyrion-core.home`, so node
configuration uses `http://kyrion-core.home:8080` instead of a numeric IPv4
address. Router DNS follows DHCP changes without making an address part of the
Kyrion contract. The Windows firewall must still restrict port 8080 to the
reserved Ethernet and Wi-Fi addresses of `kyrion-node`; the DNS name does not
replace authentication or firewall policy.

After Web is running, the authenticated `/settings/services` page provides a
five-second overview of Web, Core, AI, Ollama and STT reachability plus the
latest Core-confirmed gateway service heartbeat. It intentionally exposes only
bounded status, host, port and latency metadata. Starting or restarting a
service is available for Windows development through the separate local recovery
surface below. Production lifecycle controls remain unavailable.

### Local recovery when Core is unavailable

On Windows, `pnpm dev` in `apps/web` now ensures the independent operator helper
is running before Web starts. It reuses an authenticated existing helper and
never replaces an occupied port. To start it separately from the repository root:

```powershell
# Optional: use the node's trusted DNS name or reserved address.
$env:KYRION_RECOVERY_PI_HOST = 'kyrion-node.local'
node infrastructure/dev-recovery.mjs
```

Open `http://localhost:3000/recovery`, also linked from Login and System services
in development mode. Enter the locally generated key from
`.run/dev-recovery/operator.key`. Keep this host administration credential private;
it is never automatically sent to the browser. The helper must remain running.
The proxy is disabled in production and accepts same-origin loopback requests
on port 3000 only. It cannot recover a stopped Web server or start itself.

**Start missing services** starts PostgreSQL using the existing Compose file,
then Ollama, Core, AI, Parakeet and the existing Chatterbox runtime in
`/training/chatterbox-venv`. Docker Desktop must already be running.
Core uses the existing `services/core/build/libs/kyrion-core-0.1.0-SNAPSHOT.jar`
and Java on PATH (Java 21 or newer); build that jar with `bootJar` after Core
changes. `JAVA_HOME`, when set, selects its Java runtime instead. An explicit
`KYRION_RECOVERY_CORE_JAR` operator environment variable can select an existing
artifact from a recovery worktree. Select an artifact matching the installed
database; the helper never repairs Flyway history or disables validation.
For persistent operator settings, create the ignored, local
`.run/dev-recovery/settings.json` with optional string fields `coreJar` (absolute
JAR path) and `piHost` (trusted node hostname/address). Environment overrides take
precedence. These values are never accepted from Web. The helper restricts its
local state directory and operator-key ACL to the invoking Windows account.
Core starts from an immutable local copy, so subsequent builds do not replace
resources beneath a running JVM. This avoids requiring Gradle during startup.
Existing Spring environment-file loading remains in effect. The helper inherits
operator environment variables, including any deliberately configured Core bind.

**Restart Windows / Pi services** requires confirmation and restarts only live
Windows processes launched by the current helper, plus the configured Pi units.
Externally launched Windows processes, PostgreSQL and running WSL speech services
are preserved; it is not a full-machine restart. Web remains running. If the
helper was restarted, older Windows processes are treated as external.

Live testing found WSL/Docker interruptions when terminating speech runtimes,
including targeted Linux SIGTERM. Therefore WSL speech restart is intentionally
excluded on this host. Missing STT/TTS runtimes can start, but running ones are
preserved. The helper never terminates WSL or its Windows process tree. Resolving
this host runtime problem is separate from these bounded recovery controls.

The updated helper waits for `SELECT 1` before starting Core, allowing up to ten
minutes for PostgreSQL crash recovery without recreating its container. An
unavailable database blocks Core, while optional independent services can still
start. Service results validate their HTTP health body rather than only an open
socket. TTS has a fifteen-minute bounded initialization window; an existing
loading helper-managed process is reused instead of launching another copy.
AI health still confirms the AI process/configuration, not successful inference.
Use System services and an intentional chat/voice check for end-to-end acceptance.
Per-service logs and a correlated operator JSONL
audit live below `.run/dev-recovery/`, separately from the Core activity log.
When `KYRION_RECOVERY_PI_HOST` is configured in the helper's environment, it also
starts/restarts the existing Spotify receiver, Voice Satellite and media player
user units over SSH as `flodinho`. It uses the existing
`~/.ssh/kyrion_node_ed25519` identity and strictly checks the known
`kyrion-node.local` host key even when connecting to a reserved IP address.
It cannot enrol a new host or manage privileged gateway/container services.
Without this optional setting only Windows services are managed.
See [ADR 0026](adr/0026-local-development-service-recovery.md).
The [local acceptance record](status/2026-10-22-local-service-recovery.md)
documents the installed artifact selection, successful live checks and WSL limit.

Source changes do not update an already running helper. Inspect its reported
`helperVersion` before acceptance; the readiness implementation is
`2026-10-30-readiness-v4`. Replacing a running helper/runtime is a separate local
operator rollout. The October 30 stabilization checks do not claim deployment or
a complete Windows/Pi host reboot.

### Chatterbox cold initialization

The Chatterbox runtime loads existing cached model files only. It never resolves
or downloads a newer Hugging Face revision at service startup. Provision/review
weights separately. In the **WSL runtime process environment**, optional
`KYRION_CHATTERBOX_MODEL_DIRECTORY` selects an existing reviewed snapshot,
`KYRION_CHATTERBOX_REFERENCE` selects existing private reference audio, and
`KYRION_CHATTERBOX_DEVICE` selects `cuda` (default) or `cpu`. These settings are
not automatically read from the AI-service `.env` or Windows environment by WSL.
Defaults preserve the existing cache and reference location.

`/live` stays available during background loading; `/ready` returns 503 until
weights, reference conditioning and warmup succeed. `/health` reports bounded
stage/error metadata without private paths. Transient local I/O gets at most
three attempts; configuration failures remain visible. Startup stage durations
are logged. The measured isolated GPU initialization took 108.8 seconds; this
does not guarantee a maximum on another host or a cold disk cache. Missing cache,
reference audio, unavailable GPU and insufficient VRAM require operator diagnosis.

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

### 4. Start local Parakeet STT

Kyrion's default development STT is NVIDIA Parakeet TDT 0.6B v3 behind the
provider-neutral OpenAI-compatible HTTP boundary. The model and native
NeMo-Speech.cpp runtime live in the isolated `Kyrion-Voice-Training` WSL
distribution and listen on loopback only from the Windows host's perspective:

```powershell
wsl.exe -d Kyrion-Voice-Training -- /training/tools/nemo-speech-install/bin/nemo-speech serve `
  --host 0.0.0.0 --port 8040 `
  --asr-model /training/models/parakeet-tdt-0.6b-v3/parakeet-tdt-0.6b-v3.q8_0.gguf `
  --device cpu --no-ui --access-log
```

Verify it at `http://127.0.0.1:8040/health`. Keep the Satellite's upstream VAD
enabled: the preserved noise gate showed short hallucinations on three of six
noise-only clips when audio was submitted to Parakeet without VAD filtering.
The HTTP boundary deliberately contains no fallback to Faster-Whisper, so an
unavailable STT runtime is visible instead of silently changing recognition
behaviour.

### 5. Start the Kyrion AI service

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

### 6. Start Kyrion Web

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

Flyway validates and applies the migration chain through the checked-out version
(currently V33 in this recovery worktree). No login user is created automatically.
Never edit an already-applied migration, including formatting-only edits.

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

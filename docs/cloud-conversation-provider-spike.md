# Cloud conversation provider spike

## Status and boundary

This is an isolated, opt-in experiment. It does not replace the normal Voice
Satellite dialogue runner, Core-owned voice sessions, local intent/action path,
Faster-Whisper, reviewed responses, or Velora TTS. The default is disabled and
opening no cloud connection or background task. Cloud endpoints expose
conversation only and no tools or device commands.

The manual start command is the spike's explicit consent mechanism. Automatic
knowledge-intent detection and a Core-persisted `LOCAL -> CLOUD_PENDING ->
CLOUD_ACTIVE -> CLOUD_ENDING` transition are intentionally not added: doing so
would make this provider comparison invasive before it has demonstrated value.
Stopping the command, inactivity, the spoken end phrase, or a provider error
closes the ephemeral session and leaves the ordinary satellite service
unchanged.

## Architecture analysis

The reusable path is:

```text
Spike command on Voice Satellite
  ALSA 16 kHz PCM16 -> existing utterance VAD/capture
      -> AI service ephemeral CloudConversationManager
          Gemini: persistent Live API session, PCM16 audio -> PCM16 audio
          OpenRouter: existing STT -> streaming text -> existing Velora TTS
      -> existing PipeWire WAV playback
```

Provider keys exist only in the AI-service environment. They are not sent to
the browser or Voice Satellite. The AI service owns language capabilities, but
Core remains the only action authority. The spike bypasses Core only for
non-executable conversation audio; it cannot propose or execute tools.

The normal wake word, local dialogue runner, Core conversation persistence,
action orchestrator, response-plan resolver, TTS providers, PCM streaming work,
and satellite service configuration are not modified. A future production
slice should place a provider-neutral cloud-session policy in Core and proxy
streaming audio through authenticated Core contracts.

## Providers

Gemini uses the official `google-genai` SDK and the currently documented
`gemini-3.1-flash-live-preview` model. Input is raw mono PCM16 at 16 kHz;
response audio is raw mono PCM16 at 24 kHz. One stateful Live API WebSocket is
kept per ephemeral spike session. Input and output transcription are enabled,
and the existing Velora voice system prompt is reused. The current hardware
adapter sends one VAD-bounded utterance and buffers one response before
playback. Consequently it proves native audio and follow-up context, but not
full duplex playback or barge-in. Continuous PCM uplink, interruption-driven
PipeWire cancellation, session resumption, and context compression remain
explicit follow-up work.

The official Live API documentation states that audio-only sessions without
compression are limited to 15 minutes and WebSocket connections to about 10
minutes. Resumption handles remain valid for two hours. Actual project rate
limits and free-tier availability must be checked in AI Studio; Google notes
that limits vary by tier and capacity and are not guaranteed.

OpenRouter uses `POST /api/v1/chat/completions` with SSE streaming. The default
comparison is `openrouter/free`; the fixed comparison defaults to
`openai/gpt-oss-120b:free` and is configuration-driven because free-model
availability changes. The router randomly chooses a compatible free model and
returns the actual model in the response. The fixed `:free` model improves
repeatability but can disappear or be capacity-limited. Session history is
ephemeral and capped at 12 messages. No transcript, audio, or history is
persisted. OpenRouter documents 50 free-model requests per day for accounts
without at least USD 10 purchased credits and 1,000 per day otherwise, with
provider availability and additional limits still applying.

## Setup and real hardware test

Install the optional SDK only in the AI-service virtual environment:

```powershell
cd services/ai
.venv/Scripts/pip.exe install -e ".[cloud-spike,speech]"
```

Set secrets only in the local process environment and start AI on the private
LAN address reachable by the enrolled Raspberry Pi:

```powershell
$env:KYRION_CLOUD_CONVERSATION_ENABLED="true"
$env:GEMINI_API_KEY="..."
$env:OPENROUTER_API_KEY="..."
.venv/Scripts/uvicorn.exe kyrion_ai.app:app --app-dir src --host 0.0.0.0 --port 8000
```

Do not expose port 8000 to the public internet. On the Voice Satellite, use its
existing private JSON configuration and run exactly one comparison command at
a time while the ordinary satellite service is stopped to avoid competing for
the microphone:

```bash
cd /opt/kyrion/services/voice-satellite
.venv/bin/pip install -e .
.venv/bin/kyrion-cloud-conversation-spike --config /etc/kyrion/voice-satellite.json --ai-url http://AI_HOST:8000 --provider gemini
.venv/bin/kyrion-cloud-conversation-spike --config /etc/kyrion/voice-satellite.json --ai-url http://AI_HOST:8000 --provider openrouter
.venv/bin/kyrion-cloud-conversation-spike --config /etc/kyrion/voice-satellite.json --ai-url http://AI_HOST:8000 --provider openrouter-explicit
```

Each turn logs transcript, response, provider/model, first response, first
audio, completion latency, and token usage when returned. Audio content is not
logged or retained. Run: greeting, sky question, sunset follow-up, simpler
explanation, local-vs-cloud reasoning, `17 * 23`, interruption attempt, and
`Danke Velora, beende das Gespräch.` Then restart the ordinary satellite and
verify a local device command.

## Benchmark sheet

| Metric | Gemini Live | OpenRouter + Velora TTS |
| --- | ---: | ---: |
| Session startup | record from start log | record from start log |
| First response | `firstResponseMs` | `firstResponseMs` (first token) |
| First audio | `firstAudioMs` | `firstAudioMs` (after complete TTS) |
| Complete response | `completeMs` | `completeMs` |
| Follow-up | manual 1-5 | manual 1-5 |
| Interruption | not implemented in adapter | not implemented in adapter |
| German quality | manual 1-5 | manual 1-5 |
| Stability | failures/disconnects | failures/HTTP 429/503 |

No recommendation should be treated as final until both providers have been
heard on the same microphone, speaker, network, prompts, and test sequence.

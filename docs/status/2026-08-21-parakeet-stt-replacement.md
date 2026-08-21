# Parakeet STT replacement — 2026-08-21

## Reason

The productive Faster-Whisper `small/int8` path repeatedly changed critical
German Hue command words and room names. This caused valid spoken multi-room
commands to miss deterministic action routing and return the generic dialogue
acknowledgement without controlling devices. More parser substitutions would
hide recognition defects and remain unsafe for action polarity and targets.

## Selection and boundary

Kyrion now selects STT independently through `KYRION_STT_PROVIDER`. The default
is the provider-neutral `http_openai` adapter, connected on loopback to NVIDIA
Parakeet TDT 0.6B v3 running in NeMo-Speech.cpp. Faster-Whisper remains only an
explicit compatibility provider and is never selected as a silent fallback.

The chosen NVIDIA model supports German and English among 25 European
languages, is CC-BY-4.0 licensed, and uses the official 714 MB Q8 GGUF. The
existing CPU runtime avoids competing for the reference RTX 2070's 8 GB VRAM
with Ollama and TTS.

## Local evidence

The candidate was run against the preserved 20-command Delock microphone set.
It retained the meaning of the power, brightness, correction, availability and
long-form commands and corrected several Faster-Whisper errors. Notable
remaining errors were `Gaming Round` for `Gamingraum` and `schaute` for
`schalte` in one long conditional sentence. The already supported direct
`Schalte ...` command was correct. A warm HTTP request for the short German
two-lamp command completed in 0.244 seconds on CPU.

Without upstream VAD, three of six preserved noise-only clips produced short
finals (`Yeah`, `Mm-hmm`, or `Okay`). Therefore the Satellite's accepted VAD
boundary remains mandatory and the candidate does not claim to pass the older
standalone streaming-STT hard gate. This change replaces bounded final STT for
the deployed voice-action path; it does not yet introduce streaming partials.

## Operational consequence

Start NeMo-Speech.cpp on port 8040 before the AI service. The AI service sends
the WAV and explicit session locale to `/v1/audio/transcriptions`. If the local
runtime is unavailable or malformed, it returns `STT_UNAVAILABLE`; it does not
fall back to another engine or execute an action from a partial transcript.

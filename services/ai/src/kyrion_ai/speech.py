from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from threading import Event
from uuid import uuid4

import httpx

from kyrion_ai.config import Settings
from kyrion_ai.providers.xtts_streaming_tts import XttsStreamingTtsAdapter
from kyrion_ai.streaming_tts import (
    StreamingTtsContractError,
    StreamingTtsRequest,
    TtsStreamAudio,
    ValidatedStreamingTts,
)

logger = logging.getLogger("uvicorn.error.kyrion-ai.tts")


class SpeechUnavailableError(RuntimeError):
    pass


class InvalidAudioError(ValueError):
    pass


class SpeechService:
    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._stt_model = None
        self._http_client = http_client

    def transcribe(self, audio: bytes, locale: str) -> str:
        if not audio.startswith(b"RIFF") or b"WAVE" not in audio[:16]:
            raise InvalidAudioError("Expected a WAV container")
        if self._settings.stt_provider == "http_openai":
            return self._transcribe_http(audio, locale)
        if self._settings.stt_provider != "faster_whisper":
            raise SpeechUnavailableError("Configured STT provider is unsupported")
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise SpeechUnavailableError("Local STT runtime is not installed") from error
        if self._stt_model is None:
            self._stt_model = WhisperModel(
                self._settings.stt_model,
                device=self._settings.stt_device,
                compute_type=self._settings.stt_compute_type,
            )
        descriptor, source_name = tempfile.mkstemp(suffix=".wav")
        os.close(descriptor)
        source = Path(source_name)
        try:
            source.write_bytes(audio)
            segments, _ = self._stt_model.transcribe(
                str(source),
                language=locale,
                beam_size=5,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()
        finally:
            source.unlink(missing_ok=True)

    def _transcribe_http(self, audio: bytes, locale: str) -> str:
        client = self._http_client or httpx.Client(timeout=30.0)
        owns_client = self._http_client is None
        try:
            response = client.post(
                f"{self._settings.http_stt_url}/v1/audio/transcriptions",
                files={"file": ("utterance.wav", audio, "audio/wav")},
                data={"language": locale, "response_format": "json"},
            )
            response.raise_for_status()
            payload = response.json()
            text = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(text, str):
                raise SpeechUnavailableError("Local HTTP STT returned an invalid response")
            return text.strip()
        except (httpx.HTTPError, ValueError) as error:
            raise SpeechUnavailableError("Local HTTP STT request failed") from error
        finally:
            if owns_client:
                client.close()

    def voices(self) -> dict[str, object]:
        if self._settings.tts_provider == "xtts":
            self._require_xtts_opt_in()
            return self._http_tts_request("GET", "/v1/voices", force_batch=True).json()
        if self._settings.tts_provider not in {"http_batch", "qwen"}:
            return {"defaultVoiceId": self._settings.default_voice_id, "voices": []}
        return self._http_tts_request("GET", "/v1/voices").json()

    def synthesize(self, text: str, voice_id: str | None = None, locale: str = "de") -> bytes:
        if self._settings.tts_provider == "xtts":
            self._require_xtts_opt_in()
            return self._synthesize_xtts_with_fallback(
                text, voice_id or self._settings.default_voice_id, locale
            )
        if self._settings.tts_provider in {"http_batch", "qwen"}:
            return self._synthesize_http(text, voice_id or self._settings.default_voice_id)
        if self._settings.tts_provider != "piper":
            raise SpeechUnavailableError("Configured TTS provider is unsupported")
        return self._synthesize_piper(text)

    def _http_tts_request(
        self, method: str, path: str, *, force_batch: bool = False, **kwargs
    ) -> httpx.Response:
        client = self._http_client or httpx.Client(timeout=120.0)
        owns_client = self._http_client is None
        base_url = (
            self._settings.qwen_tts_url
            if self._settings.tts_provider == "qwen" and not force_batch
            else self._settings.http_tts_url
        )
        try:
            response = client.request(method, f"{base_url}{path}", **kwargs)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise SpeechUnavailableError("Local HTTP TTS request failed") from error
        finally:
            if owns_client:
                client.close()
        return response

    def _require_xtts_opt_in(self) -> None:
        if not self._settings.xtts_experimental_enabled:
            raise SpeechUnavailableError("Experimental XTTS provider is not enabled")

    def _synthesize_xtts_with_fallback(self, text: str, voice_id: str, locale: str) -> bytes:
        started = time.perf_counter()
        reason = "unknown"
        try:
            owns_client = self._http_client is None
            client = self._http_client or httpx.Client(
                timeout=httpx.Timeout(self._settings.xtts_timeout_seconds)
            )
            try:
                stream = ValidatedStreamingTts(
                    XttsStreamingTtsAdapter(self._settings.xtts_tts_url, client)
                )
                request = StreamingTtsRequest(uuid4(), text, locale, voice_id, 0, True)
                chunks: list[bytes] = []
                arrivals: list[float] = []
                for event in stream.stream(request, Event()):
                    if isinstance(event, TtsStreamAudio):
                        chunks.append(event.pcm)
                        arrivals.append(time.perf_counter() - started)
                pcm = b"".join(chunks)
                sample_rate = stream.capabilities.sample_rate
                duration = len(pcm) / (sample_rate * 2)
                maximum_duration = _maximum_expected_duration(text)
                if duration <= 0 or duration > maximum_duration:
                    reason = "suspicious_duration"
                    raise StreamingTtsContractError("XTTS_SUSPICIOUS_DURATION")
                total = time.perf_counter() - started
                underruns = _playback_underruns(arrivals, chunks, sample_rate)
                logger.info(
                    "tts provider=xtts-experimental ttfa_seconds=%.3f rtf=%.3f "
                    "underruns=%d audio_seconds=%.3f text_characters=%d fallback_reason=none",
                    arrivals[0],
                    total / duration,
                    underruns,
                    duration,
                    len(text),
                )
                return _pcm_to_wav(pcm, sample_rate)
            finally:
                if owns_client:
                    client.close()
        except (StreamingTtsContractError, httpx.HTTPError, TimeoutError) as error:
            if reason == "unknown":
                reason = (
                    "timeout" if isinstance(error, httpx.TimeoutException) else "provider_failure"
                )
            logger.warning(
                "tts provider=xtts-experimental fallback_provider=chatterbox "
                "fallback_reason=%s text_characters=%d error=%s",
                reason,
                len(text),
                type(error).__name__,
            )
            return self._synthesize_http(text, voice_id, force_batch=True)

    def _synthesize_http(self, text: str, voice_id: str, *, force_batch: bool = False) -> bytes:
        response = self._http_tts_request(
            "POST",
            "/v1/synthesize",
            force_batch=force_batch,
            json={"text": text, "voiceId": voice_id},
        )
        if not response.content.startswith(b"RIFF"):
            raise SpeechUnavailableError("Local HTTP TTS returned invalid audio")
        return response.content

    def _synthesize_piper(self, text: str) -> bytes:
        executable = self._settings.piper_executable
        model = self._settings.piper_model
        if not executable or not model:
            raise SpeechUnavailableError("Local TTS runtime is not configured")
        if not Path(executable).is_file() or not Path(model).is_file():
            raise SpeechUnavailableError("Local TTS executable or model is unavailable")
        descriptor, output_name = tempfile.mkstemp(suffix=".wav")
        os.close(descriptor)
        output = Path(output_name)
        try:
            result = subprocess.run(
                [executable, "--model", model, "--output_file", str(output)],
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                raise SpeechUnavailableError("Local TTS synthesis failed")
            return output.read_bytes()
        finally:
            output.unlink(missing_ok=True)


# Compatibility name for callers that only use local STT.
LocalSpeechService = SpeechService


def _maximum_expected_duration(text: str) -> float:
    # Deliberately generous output validation, not language or vocabulary filtering.
    words = len(text.split())
    return max(4.0, words * 1.25 + 2.0)


def _playback_underruns(arrivals: list[float], chunks: list[bytes], sample_rate: int) -> int:
    durations = [len(chunk) / (sample_rate * 2) for chunk in chunks]
    buffered = 0.0
    start_index = None
    for index, duration in enumerate(durations):
        buffered += duration
        if buffered >= 0.320:
            start_index = index
            break
    if start_index is None:
        return 1
    underruns = 0
    previous = arrivals[start_index]
    for index in range(start_index + 1, len(arrivals)):
        buffered -= arrivals[index] - previous
        if buffered < 0:
            underruns += 1
            buffered = 0.0
        buffered += durations[index]
        previous = arrivals[index]
    return underruns


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()

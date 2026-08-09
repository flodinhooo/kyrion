from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import httpx

from kyrion_ai.config import Settings


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

    def voices(self) -> dict[str, object]:
        if self._settings.tts_provider != "qwen":
            return {"defaultVoiceId": self._settings.default_voice_id, "voices": []}
        return self._qwen_request("GET", "/v1/voices").json()

    def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        if self._settings.tts_provider == "qwen":
            return self._synthesize_qwen(text, voice_id or self._settings.default_voice_id)
        if self._settings.tts_provider != "piper":
            raise SpeechUnavailableError("Configured TTS provider is unsupported")
        return self._synthesize_piper(text)

    def _qwen_request(self, method: str, path: str, **kwargs) -> httpx.Response:
        client = self._http_client or httpx.Client(timeout=120.0)
        owns_client = self._http_client is None
        try:
            response = client.request(method, f"{self._settings.qwen_tts_url}{path}", **kwargs)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise SpeechUnavailableError("Local Qwen TTS request failed") from error
        finally:
            if owns_client:
                client.close()
        return response

    def _synthesize_qwen(self, text: str, voice_id: str) -> bytes:
        response = self._qwen_request(
            "POST", "/v1/synthesize", json={"text": text, "voiceId": voice_id}
        )
        if not response.content.startswith(b"RIFF"):
            raise SpeechUnavailableError("Local Qwen TTS returned invalid audio")
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

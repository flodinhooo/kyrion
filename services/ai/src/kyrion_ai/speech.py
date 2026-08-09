from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from kyrion_ai.config import Settings


class SpeechUnavailableError(RuntimeError):
    pass


class InvalidAudioError(ValueError):
    pass


class LocalSpeechService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stt_model = None

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
        with tempfile.NamedTemporaryFile(suffix=".wav") as source:
            source.write(audio)
            source.flush()
            segments, _ = self._stt_model.transcribe(
                source.name,
                language=locale,
                beam_size=5,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()

    def synthesize(self, text: str) -> bytes:
        executable = self._settings.piper_executable
        model = self._settings.piper_model
        if not executable or not model:
            raise SpeechUnavailableError("Local TTS runtime is not configured")
        if not Path(executable).is_file() or not Path(model).is_file():
            raise SpeechUnavailableError("Local TTS executable or model is unavailable")
        with tempfile.NamedTemporaryFile(suffix=".wav") as output:
            result = subprocess.run(
                [executable, "--model", model, "--output_file", output.name],
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                raise SpeechUnavailableError("Local TTS synthesis failed")
            output.seek(0)
            return output.read()

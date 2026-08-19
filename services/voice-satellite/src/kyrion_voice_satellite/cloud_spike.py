from __future__ import annotations

import argparse
import base64
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path

from kyrion_voice_satellite.audio import AlsaCapture
from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.playback import PipeWirePlayback
from kyrion_voice_satellite.utterance import capture_utterance
from kyrion_voice_satellite.vad import WebRtcVoiceActivityDetector
from kyrion_voice_satellite.wav import pcm_to_wav

LOGGER = logging.getLogger("kyrion-cloud-conversation-spike")


class SpikeClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def open(self, provider: str, locale: str) -> dict[str, object]:
        return self._json("POST", "/v1/cloud-conversations/sessions", {
            "provider": provider, "locale": locale,
        })

    def turn(self, session_id: str, audio: bytes) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.base_url}/v1/cloud-conversations/sessions/{session_id}/turns",
            data=audio,
            headers={"Content-Type": "audio/wav"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                value = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError("Cloud turn failed") from error
        if not isinstance(value, dict):
            raise RuntimeError("Cloud turn returned an invalid response")
        return value

    def close(self, session_id: str) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/v1/cloud-conversations/sessions/{session_id}", method="DELETE"
        )
        with urllib.request.urlopen(request, timeout=15):
            pass

    def _json(self, method: str, path: str, body: dict[str, str]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=json.dumps(body).encode(), method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
        if not isinstance(value, dict):
            raise RuntimeError("Cloud service returned an invalid response")
        return value


def run(config: SatelliteConfig, ai_url: str, provider: str) -> None:
    client = SpikeClient(ai_url)
    session = client.open(provider, config.locale)
    session_id = str(session["sessionId"])
    LOGGER.info("Cloud session active provider=%s model=%s", session["provider"], session["model"])
    playback = PipeWirePlayback(config.playback_target)
    vad = WebRtcVoiceActivityDetector()
    try:
        while True:
            LOGGER.info("Listening; Ctrl+C ends the spike")
            utterance = capture_utterance(
                AlsaCapture(config.capture_device).frames(), vad,
                start_timeout_seconds=config.speech_start_timeout_seconds,
                end_silence_seconds=config.speech_end_silence_seconds,
                max_seconds=config.utterance_max_seconds,
            )
            if utterance is None:
                LOGGER.info("Cloud session ended after inactivity")
                break
            result = client.turn(session_id, pcm_to_wav(utterance.pcm))
            LOGGER.info("Transcript: %s", result.get("transcript", ""))
            LOGGER.info("Response: %s", result.get("responseText", ""))
            LOGGER.info("Metrics: %s", json.dumps(result.get("metrics", {}), ensure_ascii=False))
            audio = base64.b64decode(str(result["audioBase64"]), validate=True)
            playback.play(audio)
            transcript = str(result.get("transcript", "")).casefold()
            if any(phrase in transcript for phrase in ("beende das gespräch", "stop cloud", "end conversation")):
                break
    finally:
        client.close(session_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolated Kyrion cloud conversation hardware spike")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--ai-url", required=True)
    parser.add_argument(
        "--provider", required=True, choices=("gemini", "openrouter", "openrouter-explicit")
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(SatelliteConfig.load(args.config), args.ai_url, args.provider)


if __name__ == "__main__":
    main()

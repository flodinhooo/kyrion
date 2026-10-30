"""Run in the Pi's installed Voice Satellite venv; no capture or playback."""

from __future__ import annotations

import io
import json
import urllib.request
import wave
from collections.abc import Callable
from pathlib import Path

from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.core_client import CoreVoiceClient


def core_ready(base_url: str) -> bool:
  try:
    with urllib.request.urlopen(
      base_url.rstrip("/") + "/actuator/health", timeout=3
    ) as response:
      return response.status == 200 and json.load(response).get("status") == "UP"
  except (OSError, ValueError):
    return False


def probe(
  config: SatelliteConfig,
  ready: Callable[[str], bool] = core_ready,
  factory: Callable[[str, str, Path], CoreVoiceClient] = CoreVoiceClient,
) -> dict[str, object]:
  result: dict[str, object] = {
    "networkReady": False,
    "authenticatedSessionOpened": False,
    "greetingValid": False,
    "sessionClosed": False,
    "microphoneOpened": False,
    "playbackPerformed": False,
  }
  if not config.core_url or not config.satellite_id or not config.credential_file:
    return {**result, "code": "VOICE_CONFIG_MISSING"}
  if not ready(config.core_url):
    return {**result, "code": "CORE_UNREACHABLE"}
  result["networkReady"] = True
  client = factory(config.core_url, config.satellite_id, config.credential_file)
  session = None
  try:
    session = client.open_session()
    result["authenticatedSessionOpened"] = True
    audio = client.greeting(session.id, config.locale)
    with wave.open(io.BytesIO(audio)) as wav:
      result["greetingValid"] = wav.getnframes() > 0 and wav.getnchannels() in (1, 2)
      result["sampleRate"] = wav.getframerate()
  except (OSError, RuntimeError, ValueError, wave.Error) as error:
    result["code"] = type(error).__name__
  finally:
    if session is not None:
      try:
        client.close_session(session.id, "explicit")
        result["sessionClosed"] = True
      except (OSError, RuntimeError) as error:
        result["closeCode"] = type(error).__name__
  return result


if __name__ == "__main__":
  configuration = SatelliteConfig.load(Path.home() / ".config/kyrion/voice-satellite.json")
  summary = probe(configuration)
  print(json.dumps(summary))
  raise SystemExit(
    0
    if all(
      summary[key]
      for key in (
        "networkReady",
        "authenticatedSessionOpened",
        "greetingValid",
        "sessionClosed",
      )
    )
    else 1
  )

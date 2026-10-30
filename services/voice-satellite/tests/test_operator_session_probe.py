import importlib.util
import io
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from kyrion_voice_satellite.config import SatelliteConfig

spec = importlib.util.spec_from_file_location(
  "operator_voice_probe",
  Path(__file__).parents[3] / "infrastructure/dev/Probe-VoiceSession.py",
)
probe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_module)


def configuration(tmp_path):
  return SatelliteConfig(
    model_path=tmp_path / "wake.onnx",
    capture_device="hw:1,0",
    core_url="http://core.test:8080",
    satellite_id="satellite",
    credential_file=tmp_path / "credential",
  )


def test_no_service_credential_is_used_when_core_is_unreachable(tmp_path):
  factory = Mock()
  result = probe_module.probe(configuration(tmp_path), lambda _: False, factory)
  assert result["code"] == "CORE_UNREACHABLE"
  assert result["authenticatedSessionOpened"] is False
  factory.assert_not_called()


def test_failed_greeting_closes_only_the_new_probe_session_without_leaking_errors(tmp_path):
  client = Mock()
  client.open_session.return_value = SimpleNamespace(id="new-probe-session")
  client.greeting.side_effect = RuntimeError("private token or provider error")
  result = probe_module.probe(configuration(tmp_path), lambda _: True, Mock(return_value=client))
  assert result["greetingValid"] is False
  assert result["sessionClosed"] is True
  assert "private" not in str(result)
  client.close_session.assert_called_once_with("new-probe-session", "explicit")


def test_greeting_is_validated_without_opening_microphone_or_speaker(tmp_path):
  output = io.BytesIO()
  with wave.open(output, "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(24000)
    wav.writeframes(b"\0" * 480)
  client = Mock()
  client.open_session.return_value = SimpleNamespace(id="new-probe-session")
  client.greeting.return_value = output.getvalue()
  result = probe_module.probe(configuration(tmp_path), lambda _: True, Mock(return_value=client))
  assert result["greetingValid"] is True
  assert result["sampleRate"] == 24000
  assert result["playbackPerformed"] is False
  assert result["microphoneOpened"] is False

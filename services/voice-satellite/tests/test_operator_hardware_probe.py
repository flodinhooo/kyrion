import importlib.util
import io
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from kyrion_voice_satellite.core_client import CoreVoiceError

spec = importlib.util.spec_from_file_location(
    "hardware_probe", Path(__file__).parents[3] / "infrastructure/dev/Probe-VeloraHardware.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_fixture_requires_mono_pcm16_at_16khz(tmp_path):
    fixture = tmp_path / "synthetic.wav"
    for rate in [16000, 24000]:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as audio:
            audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0" * 320)
        fixture.write_bytes(buffer.getvalue())
        if rate == 16000:
            assert module.fixture_audio(fixture) == buffer.getvalue()
        else:
            with pytest.raises(ValueError, match="FIXTURE_FORMAT_INVALID"):
                module.fixture_audio(fixture)


@pytest.mark.parametrize("suffix", ["/execute", "/playback-completed"])
def test_hardware_probe_never_authorizes_device_actions(tmp_path, suffix):
    client = module.SafeClient("http://core", "synthetic", tmp_path / "absent-credential")
    with pytest.raises(CoreVoiceError, match="OPERATOR_PROBE_ACTION_FORBIDDEN"):
        client._request("POST", "/synthetic" + suffix, b"", "application/json")


def test_software_status_never_claims_audibility_or_first_model_token(monkeypatch):
    monkeypatch.setattr(module.SatelliteConfig, "load", lambda _path: object())
    monkeypatch.setattr(module, "WebRtcVoiceActivityDetector", lambda: object())
    result = module.probe(SimpleNamespace(fixture=None, capture_seconds=0, dialogue=False))
    assert result["audibilityVerified"] is False
    assert result["firstAudibleAudioMs"] is None
    assert result["firstModelOutputMs"] is None
    assert result["microphoneOpened"] is False


def test_processing_audio_does_not_mark_answer_or_first_model_output():
    result = {}
    module.observe_event(result, {"type": "audio.chunk"}, 10)
    assert result == {}
    module.observe_event(result, {"type": "transcript"}, 20)
    module.observe_event(result, {"type": "model.first_delta"}, 30)
    assert result == {"captureEndToTranscriptMs": 20, "firstModelOutputMs": 30}
    module.observe_event(result, {"type": "answer.started"}, 40)
    assert result["answerStarted"] is True
    assert "captureEndToAnswerAudioMs" not in result

import importlib.util
import io
import wave
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "isolated_tts", Path(__file__).with_name("Benchmark-IsolatedTts.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_truncated_audio_is_not_accepted_as_playable(tmp_path):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0" * 320)
    path = tmp_path / "synthetic.wav"
    path.write_bytes(output.getvalue())
    assert module.wav_info(path)["audioSeconds"] == 0.01
    path.write_bytes(output.getvalue()[:-2])
    with pytest.raises(ValueError, match="EMPTY_OR_TRUNCATED_WAV"):
        module.wav_info(path)


def test_first_requests_are_excluded_from_warm_summary():
    rows = []
    for case in module.CASES:
        rows.append(
            {"case": case, "phase": "first_use_text", "firstPlayableSeconds": 100}
        )
        rows += [
            {
                "case": case,
                "phase": "warm",
                "firstPlayableSeconds": value,
                "rtf": value / 2,
                "audioSeconds": 2,
            }
            for value in [1, 2, 3]
        ]
    assert module.summarize(rows)["short"]["medianFirstPlayableSeconds"] == 2
    with pytest.raises(ValueError, match="EXACTLY_THREE_WARM_RUNS_REQUIRED"):
        module.summarize(rows[:-1])

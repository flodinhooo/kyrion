import hashlib
import importlib.util
import json
import struct
import wave
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "listening", Path(__file__).with_name("Prepare-TtsListening.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_wav(path, values, rate=1000):
    with wave.open(str(path), "wb") as audio:
        audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        audio.writeframes(struct.pack(f"<{len(values)}h", *values))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_signal_analysis_and_identity_gate(tmp_path):
    path = tmp_path / "synthetic.wav"
    digest = write_wav(path, [0] * 100 + [10000] * 200 + [0] * 100)
    result = module.inspect_wav(path, digest)
    assert result["audioSeconds"] == pytest.approx(0.4)
    assert result["quietSeconds"] == pytest.approx(0.2)
    assert result["leadingQuietSeconds"] == pytest.approx(0.1)
    assert result["trailingQuietSeconds"] == pytest.approx(0.1)
    assert result["exactRepeatedNonquiet20msBlocks"] == 9
    with pytest.raises(ValueError, match="SHA256_MISMATCH"):
        module.inspect_wav(path, "0" * 64)
    path.write_bytes(path.read_bytes()[:-2])
    with pytest.raises(ValueError, match="TRUNCATED"):
        module.inspect_wav(path, hashlib.sha256(path.read_bytes()).hexdigest())


@pytest.fixture
def corpus(tmp_path):
    texts = {case: f"<Solltext {case}>" for case in module.CASES}
    for engine in module.ENGINES:
        directory = tmp_path / engine
        directory.mkdir()
        rows = []
        for case in module.CASES:
            for iteration in range(4):
                path = directory / f"{case}-{iteration}.wav"
                digest = write_wav(path, [1000 + iteration] * 100)
                rows.append(
                    {
                        "case": case,
                        "iteration": iteration,
                        "wav": path.name,
                        "sha256": digest,
                        "audioSeconds": 0.1,
                        "totalSeconds": 100 - iteration,
                    }
                )
        (directory / "results.json").write_text(
            json.dumps({"metadata": {"texts": texts}, "runs": rows})
        )
    return tmp_path


def test_fixed_selection_escaping_and_reveal(corpus):
    audit = module.build_audit(corpus, False)
    page = module.render(corpus, audit, "de")
    contents = page.read_text(encoding="utf-8")
    blind = contents.split("<details>", 1)[0]
    assert "Chatterbox" not in blind and "MOSS" not in blind
    assert "&lt;Solltext short&gt;" in blind
    assert "<Solltext" not in contents
    assert len(audit["samples"]) == 24
    for case in module.CASES:
        for label, engine in zip(("A", "B"), module.ORDER[case]):
            assert (page.parent / "audio" / f"{case}-{label}.wav").read_bytes() == (
                corpus / engine / f"{case}-1.wav"
            ).read_bytes()
    assert all("id=" + '"' + case + "-choice" in blind for case in module.CASES)
    assert 'href="audit.json"' in contents


def test_rejects_different_inputs_and_unexpected_file_path(corpus):
    path = corpus / "moss" / "results.json"
    source = json.loads(path.read_text())
    source["metadata"]["texts"]["short"] = "another input"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="TEXTS_DIFFER"):
        module.build_audit(corpus, False)
    source["metadata"]["texts"]["short"] = "<Solltext short>"
    source["runs"][0]["wav"] = "../../private.wav"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="UNEXPECTED_WAV_PATH"):
        module.build_audit(corpus, False)


def test_cached_transcript_requires_same_wav_hash(corpus, monkeypatch):
    first = module.build_audit(corpus, False)
    row = first["samples"][0]
    row["stt"] = {"status": "transcribed", "text": "existing synthetic hint"}
    (corpus / "review" / "audit.json").write_text(json.dumps(first))

    def unavailable(_path):
        raise AssertionError("STT must not be called for the cached WAV")

    monkeypatch.setattr(module, "transcribe", unavailable)
    # All fixtures sharing this digest reuse the correct content-addressed hint.
    second = module.build_audit(corpus, False)
    assert second["samples"][0]["stt"]["text"] == "existing synthetic hint"
    source_path = corpus / "chatterbox" / "results.json"
    source = json.loads(source_path.read_text())
    source["runs"][0]["sha256"] = write_wav(
        corpus / "chatterbox" / "short-0.wav", [12345] * 100
    )
    source_path.write_text(json.dumps(source))
    third = module.build_audit(corpus, False)
    assert third["samples"][0]["stt"]["status"] == "not_requested"


def test_locale_resources_have_matching_keys():
    locales = json.loads(
        Path(__file__)
        .with_name("tts-listening-locales.json")
        .read_text(encoding="utf-8")
    )
    assert locales["de"].keys() == locales["en"].keys()

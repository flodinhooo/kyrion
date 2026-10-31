from types import SimpleNamespace

import pytest
from test_chatterbox_startup import runtime


@pytest.mark.parametrize("fail", [False, True])
def test_batch_phase_observation_preserves_parameters_and_restores_methods(monkeypatch, fail):
    module = runtime(monkeypatch)
    calls = []

    def tokens():
        calls.append("tokens")

    def decoder():
        calls.append("decoder")

    def conditioning():
        calls.append("conditioning")

    loaded = SimpleNamespace(
        t3=SimpleNamespace(inference=tokens),
        s3gen=SimpleNamespace(inference=decoder),
        prepare_conditionals=conditioning,
    )

    def generate(text, **parameters):
        assert text == "Synthetic input"
        assert parameters == {
            "language_id": "de",
            "cfg_weight": 0.5,
            "temperature": 0.65,
            "repetition_penalty": 2.0,
        }
        loaded.t3.inference()
        if fail:
            raise RuntimeError("synthetic failure")
        loaded.s3gen.inference()
        return "synthetic audio"

    loaded.generate = generate
    if fail:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            module.measured_generate(loaded, "Synthetic input")
    else:
        audio, metrics = module.measured_generate(loaded, "Synthetic input")
        assert audio == "synthetic audio"
        assert metrics["tokens_calls"] == metrics["decoder_calls"] == 1
        assert "conditioning_calls" not in metrics
    assert loaded.t3.inference is tokens
    assert loaded.s3gen.inference is decoder
    assert loaded.prepare_conditionals is conditioning

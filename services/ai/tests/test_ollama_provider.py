from kyrion_ai.providers.ollama import (
    _average,
    _context_length,
    _nanoseconds_to_milliseconds,
    _OllamaChatMessage,
    _OllamaChatResult,
    _tokens_per_second,
)


def test_context_length_reads_model_family_metadata() -> None:
    model_info = {
        "general.architecture": "gemma3",
        "gemma3.context_length": 131_072,
    }

    assert _context_length(model_info) == 131_072


def test_context_length_ignores_unrelated_or_invalid_values() -> None:
    assert _context_length({"gemma3.context_length": "131072"}) is None
    assert _context_length({"general.parameter_count": 4_300_000_000}) is None


def test_benchmark_metrics_convert_ollama_nanoseconds() -> None:
    result = _OllamaChatResult(
        message=_OllamaChatMessage(content="KYRION-OK"),
        total_duration=2_000_000_000,
        eval_count=40,
        eval_duration=1_000_000_000,
    )

    assert _nanoseconds_to_milliseconds(result.total_duration) == 2_000.0
    assert _tokens_per_second(result) == 40.0
    assert _average([20.0, 40.0]) == 30.0


def test_tokens_per_second_handles_missing_eval_duration() -> None:
    result = _OllamaChatResult(message=_OllamaChatMessage())

    assert _tokens_per_second(result) == 0.0

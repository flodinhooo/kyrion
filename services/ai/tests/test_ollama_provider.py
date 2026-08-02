from kyrion_ai.providers.ollama import _context_length


def test_context_length_reads_model_family_metadata() -> None:
    model_info = {
        "general.architecture": "gemma3",
        "gemma3.context_length": 131_072,
    }

    assert _context_length(model_info) == 131_072


def test_context_length_ignores_unrelated_or_invalid_values() -> None:
    assert _context_length({"gemma3.context_length": "131072"}) is None
    assert _context_length({"general.parameter_count": 4_300_000_000}) is None

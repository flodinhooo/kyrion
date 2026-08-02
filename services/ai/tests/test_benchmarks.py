import pytest

from kyrion_ai.benchmarks import (
    BenchmarkLocale,
    BenchmarkPrompt,
    benchmark_prompts,
    response_passes,
)


@pytest.mark.parametrize("locale", ["de", "en"])
def test_benchmark_suite_is_small_and_stable(locale: BenchmarkLocale) -> None:
    prompts = benchmark_prompts(locale)

    assert [prompt.id for prompt in prompts] == ["instruction", "summary", "reasoning"]
    assert all(prompt.content for prompt in prompts)


def test_exact_benchmark_check_ignores_whitespace_and_case() -> None:
    prompt = BenchmarkPrompt("instruction", "Test", expected_text="KYRION-OK")

    assert response_passes(prompt, "  kyrion-ok\n")
    assert not response_passes(prompt, "KYRION-OK with extra text")


def test_open_benchmark_check_requires_a_meaningful_response() -> None:
    prompt = BenchmarkPrompt("summary", "Test")

    assert response_passes(prompt, "First useful point")
    assert not response_passes(prompt, "Too short")

from dataclasses import dataclass
from typing import Literal

BenchmarkLocale = Literal["de", "en"]


@dataclass(frozen=True)
class BenchmarkPrompt:
    id: str
    content: str
    expected_text: str | None = None


_PROMPTS: dict[BenchmarkLocale, tuple[BenchmarkPrompt, ...]] = {
    "de": (
        BenchmarkPrompt(
            id="instruction",
            content="Antworte ausschließlich mit KYRION-OK.",
            expected_text="KYRION-OK",
        ),
        BenchmarkPrompt(
            id="summary",
            content=(
                "Fasse in genau zwei kurzen Stichpunkten zusammen: Lokale KI hält "
                "Daten unter eigener Kontrolle. Cloud-Dienste können trotzdem "
                "optional nützlich sein."
            ),
        ),
        BenchmarkPrompt(
            id="reasoning",
            content=(
                "Ein Sensor meldet 18 °C. Nach einer bestätigten Messung steigt "
                "der Wert um 3 °C. Nenne nur den neuen Wert mit Einheit."
            ),
            expected_text="21 °C",
        ),
    ),
    "en": (
        BenchmarkPrompt(
            id="instruction",
            content="Reply with KYRION-OK and nothing else.",
            expected_text="KYRION-OK",
        ),
        BenchmarkPrompt(
            id="summary",
            content=(
                "Summarise in exactly two short bullet points: Local AI keeps data "
                "under the user's control. Cloud services can still be useful as "
                "an option."
            ),
        ),
        BenchmarkPrompt(
            id="reasoning",
            content=(
                "A sensor reports 18 °C. After a confirmed measurement, the value "
                "rises by 3 °C. State only the new value with its unit."
            ),
            expected_text="21 °C",
        ),
    ),
}


def benchmark_prompts(locale: BenchmarkLocale) -> tuple[BenchmarkPrompt, ...]:
    return _PROMPTS[locale]


def response_passes(prompt: BenchmarkPrompt, response: str) -> bool:
    normalised = " ".join(response.strip().split()).casefold()
    if prompt.expected_text is not None:
        return normalised == prompt.expected_text.casefold()
    return len(normalised) >= 10

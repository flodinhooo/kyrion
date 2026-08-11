"""Retrospective, generation-free XTTS multi-signal guard evaluation.

The analysis consumes preserved EOS traces, WAVs and independent whole-output
word timestamps.  ASR is used only to label the evaluation interval; it is
never an input to a candidate guard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

SAMPLE_RATE = 24_000
FRAME_SECONDS = 0.02
SILENCE_DBFS = -40.0
MINIMUM_PAUSE_SECONDS = 0.12
EXPECTED_WORDS = ("ich", "bin", "velora")


def normalized_word(value: str) -> str:
    return "".join(re.findall(r"[a-z0-9äöüß]+", value.casefold()))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pauses(audio: np.ndarray, rate: int) -> list[dict[str, float]]:
    frame_size = round(FRAME_SECONDS * rate)
    silent: list[bool] = []
    for offset in range(0, len(audio), frame_size):
        frame = audio[offset : offset + frame_size]
        rms = float(np.sqrt(np.mean(np.square(frame, dtype=np.float64)))) if len(frame) else 0.0
        dbfs = 20.0 * math.log10(max(rms, 1e-9))
        silent.append(dbfs < SILENCE_DBFS)

    result: list[dict[str, float]] = []
    start: int | None = None
    for index, is_silent in enumerate([*silent, False]):
        if is_silent and start is None:
            start = index
        elif not is_silent and start is not None:
            duration = (index - start) * FRAME_SECONDS
            if duration >= MINIMUM_PAUSE_SECONDS:
                result.append(
                    {
                        "startSeconds": round(start * FRAME_SECONDS, 6),
                        "endSeconds": round(index * FRAME_SECONDS, 6),
                        "durationSeconds": round(duration, 6),
                    }
                )
            start = None
    return result


def top10_entropy(record: dict[str, Any]) -> float:
    probabilities = [item["probability"] for item in record["topTokens"] if item["probability"] > 0]
    covered = sum(probabilities)
    if covered < 1.0 - 1e-9:
        probabilities.append(1.0 - covered)
    return -sum(probability * math.log2(probability) for probability in probabilities)


def repetition_signals(tokens: list[int], position: int) -> dict[str, Any]:
    prefix = tokens[: position + 1]
    repeated_lengths: list[int] = []
    for size in (2, 3, 4):
        if len(prefix) >= size * 2 and tuple(prefix[-size:]) in {
            tuple(prefix[index : index + size]) for index in range(len(prefix) - size)
        }:
            repeated_lengths.append(size)

    recent = prefix[-24:]
    bigrams = [tuple(recent[index : index + 2]) for index in range(len(recent) - 1)]
    repeated_bigrams = sum(count - 1 for count in Counter(bigrams).values() if count > 1)
    return {
        "repeatedSuffixNgrams": repeated_lengths,
        "recentRepeatedBigramCount": repeated_bigrams,
    }


def signal_at(trace: list[dict[str, Any]], position: int) -> dict[str, Any]:
    position = min(max(position, 0), len(trace) - 1)
    record = trace[position]
    entropies = [top10_entropy(item) for item in trace]
    baseline = entropies[max(0, position - 20) : position]
    baseline_median = float(np.median(baseline)) if baseline else entropies[position]
    repetition = repetition_signals(
        [int(item["selectedTokenId"]) for item in trace], position
    )
    return {
        "codePosition": position,
        "eosProbability": record["eosProbability"],
        "eosSamplingProbability": record["eosSamplingProbability"],
        "eosRank": record["eosRank"],
        "top10EntropyBits": round(entropies[position], 6),
        "entropyDeltaFromPrior20MedianBits": round(
            entropies[position] - baseline_median, 6
        ),
        **repetition,
    }


def labels(short_run: dict[str, Any], duration: float) -> dict[str, Any]:
    words = short_run["transcriptWords"]
    normalized = [normalized_word(item["word"]) for item in words]
    first_three_match = len(normalized) >= 3 and all(
        observed == expected or (expected == "velora" and observed in {"velour", "veloura"})
        for observed, expected in zip(normalized[:3], EXPECTED_WORDS, strict=True)
    )
    desired_end = float(words[2]["end"]) if first_three_match else None
    fantasy_start = float(words[3]["start"]) if first_three_match and len(words) > 3 else None
    if desired_end is not None and desired_end > duration:
        desired_end = None
    if fantasy_start is not None and fantasy_start > duration:
        fantasy_start = None
    return {
        "requestedContentObserved": first_three_match,
        "desiredContentEndSeconds": desired_end,
        "firstFantasyWordStartSeconds": fantasy_start,
        "wholeOutputClean": bool(short_run["cleanEos"]),
        "labelSource": "preserved whole-output Faster-Whisper word timestamps",
    }


def candidate_decisions(events: list[dict[str, Any]]) -> dict[str, float | None]:
    def first(predicate: Any) -> float | None:
        match = next((event for event in events if predicate(event)), None)
        return match["pause"]["endSeconds"] if match else None

    return {
        "pausePlusEos": first(
            lambda event: event["signal"]["eosRank"] <= 50
            and event["signal"]["eosProbability"] >= 0.001
        ),
        "pausePlusRepeatedNgram": first(
            lambda event: len(event["signal"]["repeatedSuffixNgrams"]) >= 2
        ),
        "pausePlusRepetitionAndEntropyShift": first(
            lambda event: bool(event["signal"]["repeatedSuffixNgrams"])
            and abs(event["signal"]["entropyDeltaFromPrior20MedianBits"]) >= 0.5
        ),
    }


def classify(stop: float | None, label: dict[str, Any], control: bool) -> str:
    if stop is None:
        if control:
            return "correct-no-stop-control"
        if not label["requestedContentObserved"]:
            return "unrecoverable-requested-content-not-observed"
        if label["wholeOutputClean"]:
            return "correct-no-stop-clean-short"
        return "false-negative-hallucination"
    if control:
        return "false-positive-control-truncation"
    desired_end = label["desiredContentEndSeconds"]
    fantasy_start = label["firstFantasyWordStartSeconds"]
    if desired_end is None:
        return "cannot-be-safe-requested-content-not-observed"
    if stop < desired_end:
        return "truncation"
    if fantasy_start is not None and stop >= fantasy_start:
        return "late-after-fantasy-start"
    return "safe-window"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trace-results",
        type=Path,
        default=Path("/training/xtts-v2-eos-trace-v2/results.json"),
    )
    parser.add_argument(
        "--short-results",
        type=Path,
        default=Path("/training/xtts-v2-short-punctuation-matrix/results.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/training/xtts-v2-multisignal-retrospective.json"),
    )
    args = parser.parse_args()
    trace_data = json.loads(args.trace_results.read_text(encoding="utf-8"))
    short_data = json.loads(args.short_results.read_text(encoding="utf-8"))
    short_by_seed = {
        item["seed"]: item for item in short_data["runs"] if item["variant"] == "period"
    }

    runs: list[dict[str, Any]] = []
    for run in trace_data["runs"]:
        wav = Path(run["wav"])
        audio, rate = sf.read(wav, dtype="float32")
        if rate != SAMPLE_RATE or audio.ndim != 1:
            raise ValueError(f"unexpected WAV format: {wav}")
        duration = len(audio) / rate
        trace = run["trace"]
        events = []
        for pause in pauses(audio, rate):
            if pause["startSeconds"] == 0 or pause["endSeconds"] >= duration - 0.04:
                continue
            position = round(pause["endSeconds"] / duration * (len(trace) - 1))
            events.append({"pause": pause, "signal": signal_at(trace, position)})

        is_control = not run["caseId"].startswith("short-")
        label = (
            {
                "requestedContentObserved": True,
                "desiredContentEndSeconds": duration,
                "firstFantasyWordStartSeconds": None,
                "wholeOutputClean": True,
                "labelSource": "clean Medium/Long control; any early stop is conservative truncation",
            }
            if is_control
            else labels(short_by_seed[run["seed"]], duration)
        )
        decisions = candidate_decisions(events)
        runs.append(
            {
                "caseId": run["caseId"],
                "seed": run["seed"],
                "wav": str(wav),
                "wavSha256": sha256(wav),
                "durationSeconds": round(duration, 6),
                "generatedCodeCount": len(trace),
                "label": label,
                "pauseEvents": events,
                "candidateStopsSeconds": decisions,
                "candidateOutcomes": {
                    name: classify(stop, label, is_control) for name, stop in decisions.items()
                },
            }
        )

    names = next(iter(runs))["candidateStopsSeconds"]
    summary = {
        name: dict(Counter(run["candidateOutcomes"][name] for run in runs)) for name in names
    }
    result = {
        "purpose": "generation-free retrospective XTTS multi-signal guard evaluation",
        "guardInputs": "audio codes, code distribution summary, EOS evidence and acoustic pauses",
        "excludedGuardInputs": "ASR, text transcript and VAD-only decisions",
        "limitations": [
            "The preserved trace contains top ten probabilities, not the full code distribution.",
            "Text attention/progress was not recorded and cannot be reconstructed retrospectively.",
            "Whole-output ASR timestamps label evaluation windows only and are not guard inputs.",
        ],
        "candidateDefinitions": {
            "pausePlusEos": "pause >=120 ms AND EOS rank <=50 AND EOS probability >=0.001",
            "pausePlusRepeatedNgram": "pause >=120 ms AND at least two of suffix 2/3/4-grams occurred earlier",
            "pausePlusRepetitionAndEntropyShift": "pause >=120 ms AND repeated suffix n-gram AND |top-10 entropy delta vs prior-20 median| >=0.5 bits",
        },
        "runs": runs,
        "summary": summary,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

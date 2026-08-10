"""Offline simulation of a text-aligned streaming output guard for XTTS WAVs."""

from __future__ import annotations

import argparse
import json
import re
import wave
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

TEXTS = {
    "short-de": "Ich bin Velora.",
    "long-de": (
        "Natürlich, Flo. Ich helfe dir dabei, den Überblick zu behalten und die nächsten "
        "Schritte in Ruhe zu planen. Sag mir einfach, womit wir beginnen sollen."
    ),
    "dialogue-de": (
        "Ja, Madrid ist die Hauptstadt Spaniens. Barcelona ist ebenfalls sehr bedeutend, "
        "aber Madrid wurde zum politischen und administrativen Zentrum des Landes."
    ),
}


def normalize(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as source:
        rate = source.getframerate()
        audio = np.frombuffer(
            source.readframes(source.getnframes()), dtype="<i2"
        ).copy()
    return audio, rate


def write_wav(path: Path, audio: np.ndarray, rate: int) -> None:
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(audio.astype("<i2").tobytes())


def find_silence(audio: np.ndarray, rate: int, after_seconds: float) -> float | None:
    frame_samples = round(0.02 * rate)
    float_audio = audio.astype(np.float32) / 32768
    rms = np.array(
        [
            np.sqrt(np.mean(float_audio[index : index + frame_samples] ** 2))
            for index in range(0, len(audio), frame_samples)
            if len(audio[index : index + frame_samples])
        ]
    )
    quiet = rms < 10 ** (-40 / 20)
    start = max(0, round(after_seconds / 0.02))
    for index in range(start, len(quiet) - 14):
        if quiet[index : index + 15].all():
            return index * 0.02 + 0.20  # retain 200 ms of natural trailing silence
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    model = WhisperModel("small", device="cpu", compute_type="int8")
    results = []
    for path in args.inputs:
        text_id = next(key for key in TEXTS if key in path.name)
        expected = normalize(TEXTS[text_id])
        audio, rate = read_wav(path)
        full_float = audio.astype(np.float32) / 32768
        whisper_audio = np.interp(
            np.linspace(0, len(full_float) - 1, round(len(full_float) * 16_000 / rate)),
            np.arange(len(full_float)),
            full_float,
        ).astype(np.float32)
        matched_at = None
        matched_word_end = None
        transcript = ""
        # Simulate availability at the shared 320 ms PCM cadence.
        for available in range(
            round(0.64 * rate), len(audio) + round(0.32 * rate), round(0.32 * rate)
        ):
            available = min(available, len(audio))
            whisper_available = round(available * 16_000 / rate)
            segments, _ = model.transcribe(
                whisper_audio[:whisper_available],
                language="de",
                beam_size=1,
                temperature=0.0,
                condition_on_previous_text=False,
                word_timestamps=True,
                vad_filter=False,
            )
            words = [word for segment in segments for word in segment.words]
            transcript = " ".join(word.word.strip() for word in words)
            observed = normalize(transcript)
            prefix = " ".join(observed.split()[: len(expected.split())])
            if (
                len(prefix.split()) >= len(expected.split())
                and SequenceMatcher(None, expected, prefix).ratio() >= 0.82
            ):
                matched_at = available / rate
                matched_word_end = words[len(expected.split()) - 1].end
                break
            if available == len(audio):
                break
        cutoff = (
            find_silence(audio, rate, matched_word_end)
            if matched_word_end is not None
            else None
        )
        generous_limit = max(3.0, 1.5 + 0.09 * len(TEXTS[text_id]))
        reason = (
            "aligned-content-plus-vad" if cutoff is not None else "duration-fallback"
        )
        cutoff = min(
            cutoff if cutoff is not None else generous_limit,
            generous_limit,
            len(audio) / rate,
        )
        guarded = audio[: round(cutoff * rate)]
        target = args.output / f"guarded--{path.name}"
        write_wav(target, guarded, rate)
        results.append(
            {
                "input": str(path),
                "output": str(target),
                "textId": text_id,
                "originalSeconds": round(len(audio) / rate, 3),
                "guardedSeconds": round(len(guarded) / rate, 3),
                "matchedAtAvailableSeconds": round(matched_at, 3)
                if matched_at
                else None,
                "matchedWordEndSeconds": round(matched_word_end, 3)
                if matched_word_end
                else None,
                "generousDurationLimitSeconds": round(generous_limit, 3),
                "reason": reason,
                "probeAtMatch": transcript,
            }
        )
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    (args.output / "guard-results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

"""Bounded CPU-int8 rolling-window STT spike; not a production provider."""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

TARGET_RATE = 16_000


def load_pcm(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError(f"Expected mono PCM16 WAV: {path}")
        sample_rate = source.getframerate()
        pcm = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(np.float32)
    pcm /= 32768.0
    if sample_rate == TARGET_RATE:
        return pcm
    output_size = round(len(pcm) * TARGET_RATE / sample_rate)
    source_positions = np.arange(len(pcm), dtype=np.float64)
    target_positions = np.linspace(0, len(pcm) - 1, output_size)
    return np.interp(target_positions, source_positions, pcm).astype(np.float32)


def transcribe(model: WhisperModel, pcm: np.ndarray, language: str, vad_filter: bool) -> str:
    segments, _ = model.transcribe(
        pcm,
        language=language,
        beam_size=1,
        best_of=1,
        temperature=0.0,
        vad_filter=vad_filter,
        condition_on_previous_text=False,
        without_timestamps=True,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", choices=("de", "en"), default="de")
    parser.add_argument("--step-ms", type=int, default=800)
    parser.add_argument("--minimum-ms", type=int, default=1_600)
    parser.add_argument("--maximum-buffer-seconds", type=int, default=15)
    parser.add_argument("--vad-filter", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    loaded_at = time.perf_counter()
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    model_load_seconds = time.perf_counter() - loaded_at
    inputs = [(path, load_pcm(path)) for path in args.inputs]
    transcribe(
        model, inputs[0][1], args.language, args.vad_filter
    )  # Lazy runtime warm-up outside measurements.

    step_samples = args.step_ms * TARGET_RATE // 1_000
    minimum_samples = args.minimum_ms * TARGET_RATE // 1_000
    maximum_samples = args.maximum_buffer_seconds * TARGET_RATE
    results: list[dict[str, object]] = []
    for path, full_pcm in inputs:
        updates: list[dict[str, object]] = []
        previous = ""
        decoder_available_at = 0.0
        for available in range(step_samples, len(full_pcm) + step_samples, step_samples):
            available = min(available, len(full_pcm))
            if available < minimum_samples and available != len(full_pcm):
                continue
            audio_available_seconds = available / TARGET_RATE
            is_final = available == len(full_pcm)
            if audio_available_seconds < decoder_available_at and not is_final:
                continue
            window_start = max(0, available - maximum_samples)
            decode_started = time.perf_counter()
            text = transcribe(
                model, full_pcm[window_start:available], args.language, args.vad_filter
            )
            decode_seconds = time.perf_counter() - decode_started
            decode_scheduled_at = max(audio_available_seconds, decoder_available_at)
            decoder_available_at = decode_scheduled_at + decode_seconds
            updates.append(
                {
                    "audioAvailableSeconds": round(audio_available_seconds, 3),
                    "decodeSeconds": round(decode_seconds, 3),
                    "decodeScheduledAtSeconds": round(decode_scheduled_at, 3),
                    "emittedAtSeconds": round(decoder_available_at, 3),
                    "latencyFromAvailableSeconds": round(
                        decoder_available_at - audio_available_seconds, 3
                    ),
                    "changed": text != previous,
                    "text": text,
                }
            )
            previous = text
            if available == len(full_pcm):
                break
        results.append(
            {
                "input": str(path),
                "durationSeconds": round(len(full_pcm) / TARGET_RATE, 3),
                "updates": updates,
                "finalText": previous,
            }
        )
    payload = {
        "model": args.model,
        "device": "cpu",
        "computeType": "int8",
        "modelLoadSeconds": round(model_load_seconds, 3),
        "stepMilliseconds": args.step_ms,
        "minimumAudioMilliseconds": args.minimum_ms,
        "maximumBufferSeconds": args.maximum_buffer_seconds,
        "vadFilter": args.vad_filter,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()

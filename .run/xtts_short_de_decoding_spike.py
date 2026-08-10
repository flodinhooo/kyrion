"""Focused XTTS-v2 short-German termination spike.

This runner intentionally changes only documented decoding parameters. It uses
the immutable Velora-F reference, native incremental inference and private
output outside Git. It does not implement a provider or output guard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch
from TTS.api import TTS

ROOT = Path("/mnt/e/dev/Kyrion/kyrion")
REFERENCE = ROOT / ".run/velora-female-options/F_weiblich_klar.wav"
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
SAMPLE_RATE = 24_000
PREBUFFER_SECONDS = 0.320
STREAM_CHUNK_SIZE = 20
TEXTS = {
    "short-de": (
        "de",
        "Ich bin Velora.",
    ),
    "long-de": (
        "de",
        (
            "Natürlich, Flo. Ich helfe dir dabei, den Überblick zu behalten und die nächsten "
            "Schritte in Ruhe zu planen. Sag mir einfach, womit wir beginnen sollen."
        ),
    ),
    "dialogue-de": (
        "de",
        (
            "Ja, Madrid ist die Hauptstadt Spaniens. Barcelona ist ebenfalls sehr bedeutend, "
            "aber Madrid wurde zum politischen und administrativen Zentrum des Landes."
        ),
    ),
}
PROFILES = {
    # Exact parameters used by the first isolated benchmark.
    "baseline": {
        "temperature": 0.75,
        "length_penalty": 1.0,
        "repetition_penalty": 10.0,
        "top_k": 50,
        "top_p": 0.85,
    },
    # Isolates the documented user-facing repetition-penalty value.
    "repetition-2": {
        "temperature": 0.75,
        "length_penalty": 1.0,
        "repetition_penalty": 2.0,
        "top_k": 50,
        "top_p": 0.85,
    },
    # Tests the documentation's claim that a higher value yields terser output.
    "length-1_5": {
        "temperature": 0.75,
        "length_penalty": 1.5,
        "repetition_penalty": 10.0,
        "top_k": 50,
        "top_p": 0.85,
    },
    # Conservative documented settings, reducing sampling entropy without going deterministic.
    "documented-conservative": {
        "temperature": 0.65,
        "length_penalty": 1.0,
        "repetition_penalty": 2.0,
        "top_k": 50,
        "top_p": 0.8,
    },
}


def percentile(values: list[float], value: float) -> float | None:
    return round(float(np.percentile(values, value)), 6) if values else None


def playback_metrics(arrivals: list[float], durations: list[float]) -> dict[str, Any]:
    cumulative = 0.0
    start_index = None
    for index, duration in enumerate(durations):
        cumulative += duration
        if cumulative >= PREBUFFER_SECONDS:
            start_index = index
            break
    if start_index is None:
        return {"underruns": 1, "minimumBufferSeconds": 0.0}
    buffer = sum(durations[: start_index + 1])
    minimum = buffer
    previous = arrivals[start_index]
    underruns = 0
    for index in range(start_index + 1, len(arrivals)):
        buffer -= arrivals[index] - previous
        minimum = min(minimum, buffer)
        if buffer < 0:
            underruns += 1
            buffer = 0.0
        buffer += durations[index]
        previous = arrivals[index]
    return {"underruns": underruns, "minimumBufferSeconds": round(max(0.0, minimum), 6)}


def generate(
    model: Any,
    conditioning: tuple[torch.Tensor, torch.Tensor],
    profile_name: str,
    text_id: str,
    run_index: int,
    output: Path,
) -> dict[str, Any]:
    language, text = TEXTS[text_id]
    parameters = PROFILES[profile_name]
    seed = 20_000 + run_index
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.cuda.synchronize()
    started = time.perf_counter()
    arrivals: list[float] = []
    chunks: list[np.ndarray] = []
    for chunk in model.inference_stream(
        text,
        language,
        *conditioning,
        stream_chunk_size=STREAM_CHUNK_SIZE,
        overlap_wav_len=1024,
        do_sample=True,
        **parameters,
    ):
        torch.cuda.synchronize()
        arrivals.append(time.perf_counter() - started)
        chunks.append(chunk.detach().float().cpu().numpy())
    total = time.perf_counter() - started
    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    durations = [len(chunk) / SAMPLE_RATE for chunk in chunks]
    intervals = np.diff(arrivals).tolist()
    gaps = [
        arrivals[index] - arrivals[index - 1] - durations[index - 1]
        for index in range(1, len(arrivals))
    ]
    audio_duration = len(audio) / SAMPLE_RATE
    target = output / f"{profile_name}--{text_id}--run-{run_index}.wav"
    sf.write(target, audio, SAMPLE_RATE, subtype="PCM_16")
    return {
        "profile": profile_name,
        "parameters": parameters,
        "textId": text_id,
        "text": text,
        "run": run_index,
        "seed": seed,
        "wav": str(target),
        "audioDurationSeconds": round(audio_duration, 6),
        "firstPlayablePcmSeconds": round(arrivals[0], 6),
        "totalGenerationSeconds": round(total, 6),
        "rtf": round(total / audio_duration, 6),
        "chunks": len(chunks),
        "chunkIntervalMedianSeconds": percentile(intervals, 50),
        "chunkIntervalP95Seconds": percentile(intervals, 95),
        "deliveryGapMedianSeconds": percentile(gaps, 50),
        "deliveryGapP95Seconds": percentile(gaps, 95),
        "deliveryGapMaxSeconds": round(max(gaps), 6) if gaps else None,
        **playback_metrics(arrivals, durations),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/training/xtts-v2-short-de-decoding-spike")
    )
    parser.add_argument(
        "--profiles", nargs="+", choices=PROFILES, default=list(PROFILES)
    )
    parser.add_argument("--texts", nargs="+", choices=TEXTS, default=["short-de"])
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("Velora F reference checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=True)
    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    model = runtime.synthesizer.tts_model
    conditioning = model.get_conditioning_latents(audio_path=[str(REFERENCE)])
    list(
        model.inference_stream(
            "Systemstart.",
            "de",
            *conditioning,
            stream_chunk_size=STREAM_CHUNK_SIZE,
            **PROFILES["baseline"],
        )
    )
    torch.cuda.synchronize()
    runs = []
    for profile in args.profiles:
        for text_id in args.texts:
            for run_index in range(1, args.repetitions + 1):
                result = generate(
                    model, conditioning, profile, text_id, run_index, args.output
                )
                runs.append(result)
                print(
                    f"{profile} {text_id} run={run_index} duration={result['audioDurationSeconds']:.3f}s "
                    f"ttfa={result['firstPlayablePcmSeconds']:.3f}s rtf={result['rtf']:.3f}",
                    flush=True,
                )
    result = {
        "model": "tts_models/multilingual/multi-dataset/xtts_v2",
        "referenceSha256": REFERENCE_SHA256,
        "streamChunkSizeTokens": STREAM_CHUNK_SIZE,
        "profiles": PROFILES,
        "runs": runs,
    }
    target = args.output / "metrics.json"
    target.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(target)


if __name__ == "__main__":
    main()

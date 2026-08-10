"""Isolated, reproducible XTTS-v2 streaming benchmark for Velora F.

Run only in the dedicated Kyrion-Voice-Training WSL environment. The script
uses XTTS' incremental ``inference_stream`` generator and never touches Core or
the AI service. Raw results and listening WAVs belong outside Git under
``/training/xtts-v2-velora-benchmark``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil
import soundfile as sf
import torch
from TTS.api import TTS
from typing_extensions import Self

ROOT = Path("/mnt/e/dev/Kyrion/kyrion")
REFERENCE = ROOT / ".run/velora-female-options/F_weiblich_klar.wav"
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
SAMPLE_RATE = 24_000
PREBUFFER_SECONDS = 0.320
TRANSCRIPT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
    "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)
TEXTS = {
    "short-de": ("de", "Ich bin Velora."),
    "domain-de": ("de", "Velora, schalte bitte die desk lamp im Gamingraum ein."),
    "domain-en": ("en", "Velora, turn on the desk lamp in the gaming room, please."),
    "medium-de": ("de", "Ich bin Velora und begleite dich durch deinen Alltag."),
    "long-de": (
        "de",
        (
            "Natürlich, Flo. Ich helfe dir dabei, den Überblick zu behalten und die nächsten "
            "Schritte in Ruhe zu planen. Sag mir einfach, womit wir beginnen sollen."
        ),
    ),
    "numbers-de": ("de", "Heute sind es 21,5 Grad. Der Termin beginnt um 14:35 Uhr."),
    "numbers-en": ("en", "It is 21.5 degrees. Your appointment starts at 2:35 p.m."),
    "dialogue-de": (
        "de",
        (
            "Ja, Madrid ist die Hauptstadt Spaniens. Barcelona ist ebenfalls sehr bedeutend, "
            "aber Madrid wurde zum politischen und administrativen Zentrum des Landes."
        ),
    ),
}


class MemorySampler:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self.peak_rss = 0
        self.peak_vram_allocated = 0
        self.peak_vram_reserved = 0

    def _sample(self) -> None:
        process = psutil.Process()
        while not self._stop.wait(0.02):
            self.peak_rss = max(self.peak_rss, process.memory_info().rss)
            self.peak_vram_allocated = max(
                self.peak_vram_allocated, torch.cuda.memory_allocated()
            )
            self.peak_vram_reserved = max(
                self.peak_vram_reserved, torch.cuda.memory_reserved()
            )

    def __enter__(self) -> Self:
        self._sample_once()
        self._thread.start()
        return self

    def _sample_once(self) -> None:
        process = psutil.Process()
        self.peak_rss = max(self.peak_rss, process.memory_info().rss)
        self.peak_vram_allocated = max(
            self.peak_vram_allocated, torch.cuda.memory_allocated()
        )
        self.peak_vram_reserved = max(
            self.peak_vram_reserved, torch.cuda.memory_reserved()
        )

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()
        self._sample_once()


def mib(value: int) -> float:
    return round(value / 1024**2, 3)


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    return round(float(np.percentile(values, percentile_value)), 6)


def signal_metrics(audio: np.ndarray, boundaries: list[int]) -> dict[str, Any]:
    if not len(audio):
        return {"peak": 0.0, "rms": 0.0, "dcOffset": 0.0, "clippedSamples": 0}
    jumps = [
        abs(float(audio[index]) - float(audio[index - 1]))
        for index in boundaries
        if 0 < index < len(audio)
    ]
    ordinary = np.abs(np.diff(audio))
    return {
        "peak": round(float(np.max(np.abs(audio))), 6),
        "rms": round(float(np.sqrt(np.mean(np.square(audio)))), 6),
        "dcOffset": round(float(np.mean(audio)), 6),
        "clippedSamples": int(np.count_nonzero(np.abs(audio) >= 0.999)),
        "boundaryJumpMax": round(max(jumps, default=0.0), 6),
        "boundaryJumpP95": percentile(jumps, 95),
        "ordinarySampleJumpP99": percentile(ordinary.tolist(), 99),
    }


def playback_metrics(arrivals: list[float], durations: list[float]) -> dict[str, Any]:
    cumulative = 0.0
    playback_start_index = None
    for index, duration in enumerate(durations):
        cumulative += duration
        if cumulative >= PREBUFFER_SECONDS:
            playback_start_index = index
            break
    if playback_start_index is None:
        return {
            "playbackStartSeconds": None,
            "underruns": 1,
            "minimumBufferSeconds": 0.0,
        }

    playback_start = arrivals[playback_start_index]
    buffer = sum(durations[: playback_start_index + 1])
    minimum_buffer = buffer
    underruns = 0
    previous_time = playback_start
    for index in range(playback_start_index + 1, len(arrivals)):
        elapsed = arrivals[index] - previous_time
        buffer -= elapsed
        minimum_buffer = min(minimum_buffer, buffer)
        if buffer < 0:
            underruns += 1
            buffer = 0.0
        buffer += durations[index]
        previous_time = arrivals[index]
    return {
        "playbackStartSeconds": round(playback_start, 6),
        "underruns": underruns,
        "minimumBufferSeconds": round(max(0.0, minimum_buffer), 6),
    }


def run_once(
    model: Any,
    conditioning: tuple[torch.Tensor, torch.Tensor],
    text_id: str,
    run_index: int,
    stream_chunk_size: int,
    output: Path,
) -> dict[str, Any]:
    language, text = TEXTS[text_id]
    gpt_cond_latent, speaker_embedding = conditioning
    torch.manual_seed(10_000 + run_index)
    torch.cuda.manual_seed_all(10_000 + run_index)
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    started = time.perf_counter()
    arrivals: list[float] = []
    chunks: list[np.ndarray] = []
    boundaries: list[int] = []
    with MemorySampler() as memory:
        generator = model.inference_stream(
            text,
            language,
            gpt_cond_latent,
            speaker_embedding,
            stream_chunk_size=stream_chunk_size,
            overlap_wav_len=1024,
            do_sample=True,
            temperature=0.75,
            top_k=50,
            top_p=0.85,
            repetition_penalty=10.0,
        )
        for chunk in generator:
            torch.cuda.synchronize()
            arrivals.append(time.perf_counter() - started)
            audio_chunk = chunk.detach().float().cpu().numpy()
            if chunks:
                boundaries.append(sum(len(item) for item in chunks))
            chunks.append(audio_chunk)
    total_seconds = time.perf_counter() - started
    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    durations = [len(chunk) / SAMPLE_RATE for chunk in chunks]
    gaps = [
        arrivals[index] - arrivals[index - 1] - durations[index - 1]
        for index in range(1, len(arrivals))
    ]
    intervals = np.diff(arrivals).tolist()
    audio_duration = len(audio) / SAMPLE_RATE
    playback = playback_metrics(arrivals, durations)
    if run_index == 1:
        sf.write(
            output / f"{text_id}-chunk-{stream_chunk_size}.wav",
            audio,
            SAMPLE_RATE,
            subtype="PCM_16",
        )
    return {
        "textId": text_id,
        "language": language,
        "text": text,
        "run": run_index,
        "streamChunkSizeTokens": stream_chunk_size,
        "firstPlayablePcmSeconds": round(arrivals[0], 6) if arrivals else None,
        "totalGenerationSeconds": round(total_seconds, 6),
        "audioDurationSeconds": round(audio_duration, 6),
        "rtf": round(total_seconds / audio_duration, 6) if audio_duration else None,
        "chunks": len(chunks),
        "chunkDurationsSeconds": [round(value, 6) for value in durations],
        "chunkArrivalSeconds": [round(value, 6) for value in arrivals],
        "chunkIntervalMedianSeconds": percentile(intervals, 50),
        "chunkIntervalP95Seconds": percentile(intervals, 95),
        "deliveryGapMedianSeconds": percentile(gaps, 50),
        "deliveryGapP95Seconds": percentile(gaps, 95),
        "deliveryGapMaxSeconds": round(max(gaps), 6) if gaps else None,
        **playback,
        "signal": signal_metrics(audio, boundaries),
        "resources": {
            "peakProcessRssMiB": mib(memory.peak_rss),
            "peakCudaAllocatedMiB": mib(memory.peak_vram_allocated),
            "peakCudaReservedMiB": mib(memory.peak_vram_reserved),
            "ruMaxRssMiB": round(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 3
            ),
        },
    }


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        groups.setdefault(run["textId"], []).append(run)
    by_text = {}
    for text_id, items in groups.items():
        by_text[text_id] = {
            "firstPcmMedianSeconds": percentile(
                [item["firstPlayablePcmSeconds"] for item in items], 50
            ),
            "firstPcmP95Seconds": percentile(
                [item["firstPlayablePcmSeconds"] for item in items], 95
            ),
            "rtfMean": round(statistics.mean(item["rtf"] for item in items), 6),
            "rtfMax": max(item["rtf"] for item in items),
            "totalMeanSeconds": round(
                statistics.mean(item["totalGenerationSeconds"] for item in items), 6
            ),
            "underrunsTotal": sum(item["underruns"] for item in items),
            "worstDeliveryGapSeconds": max(
                (
                    item["deliveryGapMaxSeconds"]
                    for item in items
                    if item["deliveryGapMaxSeconds"] is not None
                ),
                default=None,
            ),
        }
    long_runs = groups.get("long-de", []) + groups.get("dialogue-de", [])
    return {
        "byText": by_text,
        "hardGate": {
            "firstPcmP95AtMost2s": all(
                item["firstPlayablePcmSeconds"] <= 2.0 for item in runs
            ),
            "longRtfBelow0_90": all(item["rtf"] < 0.90 for item in long_runs),
            "mediumLongNeverUnderrun": all(
                item["underruns"] == 0
                for item in runs
                if item["textId"] in {"medium-de", "long-de", "dialogue-de"}
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/training/xtts-v2-velora-benchmark")
    )
    parser.add_argument("--stream-chunk-size", type=int, default=10)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("Velora F reference checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=True)

    torch.cuda.reset_peak_memory_stats()
    load_started = time.perf_counter()
    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - load_started
    model = runtime.synthesizer.tts_model
    condition_started = time.perf_counter()
    conditioning = model.get_conditioning_latents(audio_path=[str(REFERENCE)])
    torch.cuda.synchronize()
    conditioning_seconds = time.perf_counter() - condition_started

    # Warm kernels and generator before any measured repetition.
    list(
        model.inference_stream(
            "Systemstart.",
            "de",
            *conditioning,
            stream_chunk_size=args.stream_chunk_size,
        )
    )
    torch.cuda.synchronize()
    selected = ["short-de", "domain-en"] if args.smoke else list(TEXTS)
    repetitions = 1 if args.smoke else args.repetitions
    runs = []
    for text_id in selected:
        for run_index in range(1, repetitions + 1):
            result = run_once(
                model,
                conditioning,
                text_id,
                run_index,
                args.stream_chunk_size,
                args.output,
            )
            runs.append(result)
            print(
                f"{text_id} run={run_index} ttfa={result['firstPlayablePcmSeconds']:.3f}s "
                f"rtf={result['rtf']:.3f} underruns={result['underruns']}",
                flush=True,
            )

    result = {
        "model": "tts_models/multilingual/multi-dataset/xtts_v2",
        "codePackage": "TTS==0.22.0",
        "modelLicence": "Coqui Public Model License (non-commercial use only)",
        "nonCommercialTermsAcceptedForSpike": os.environ.get("COQUI_TOS_AGREED") == "1",
        "device": torch.cuda.get_device_name(0),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "referenceSha256": REFERENCE_SHA256,
        "sampleRateHz": SAMPLE_RATE,
        "prebufferMilliseconds": int(PREBUFFER_SECONDS * 1000),
        "modelLoadSeconds": round(load_seconds, 6),
        "conditioningSeconds": round(conditioning_seconds, 6),
        "streamChunkSizeTokens": args.stream_chunk_size,
        "runs": runs,
        "summary": summarize(runs),
    }
    target = args.output / f"results-chunk-{args.stream_chunk_size}.json"
    target.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(target)


if __name__ == "__main__":
    main()

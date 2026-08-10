"""Bounded XTTS-v2 short-output punctuation and input-normalisation matrix.

Runs only in the isolated training environment. It does not implement a
provider or touch Core. Listening WAVs and raw results stay outside Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch
from faster_whisper import WhisperModel
from TTS.api import TTS

ROOT = Path("/mnt/e/dev/Kyrion/kyrion")
REFERENCE = ROOT / ".run/velora-female-options/F_weiblich_klar.wav"
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
RATE = 24_000
PREBUFFER = 0.320
CHUNK_TOKENS = 20
SEEDS = tuple(range(50_001, 50_011))
BASE = "Ich bin Velora"
VARIANTS = {
    "period": BASE + ".",
    "exclamation": BASE + "!",
    "question": BASE + "?",
    "semicolon": BASE + ";",
}
NORMALISATION_CASES = {
    "missing-terminal": BASE,
    "trailing-space": BASE + ".   ",
    "unicode-nfd": unicodedata.normalize("NFD", BASE + "."),
    "duplicate-terminal": BASE + "..",
}
PARAMETERS = {
    "temperature": 0.75,
    "top_k": 50,
    "top_p": 0.85,
    "repetition_penalty": 10.0,
}


def norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9äöüß]+", text.casefold()))


def normalize_input(text: str) -> str:
    value = unicodedata.normalize("NFC", text).strip()
    value = re.sub(r"([.!?;])\1+$", r"\1", value)
    if not re.search(r"[.!?;]$", value):
        value += "."
    return value


def playback(arrivals: list[float], durations: list[float]) -> dict[str, Any]:
    buffered = 0.0
    start = None
    for index, duration in enumerate(durations):
        buffered += duration
        if buffered >= PREBUFFER:
            start = index
            break
    if start is None:
        return {"underruns": 1, "minimumBufferSeconds": 0.0}
    minimum = buffered
    previous = arrivals[start]
    underruns = 0
    for index in range(start + 1, len(arrivals)):
        buffered -= arrivals[index] - previous
        minimum = min(minimum, buffered)
        if buffered < 0:
            underruns += 1
            buffered = 0.0
        buffered += durations[index]
        previous = arrivals[index]
    return {"underruns": underruns, "minimumBufferSeconds": round(max(0.0, minimum), 6)}


def active_end(audio: np.ndarray) -> float:
    frame = round(0.02 * RATE)
    rms = [float(np.sqrt(np.mean(audio[i : i + frame] ** 2))) for i in range(0, len(audio), frame)]
    active = [index for index, value in enumerate(rms) if value >= 10 ** (-40 / 20)]
    return round(((active[-1] + 1) * frame / RATE) if active else 0.0, 6)


def transcribe(aligner: WhisperModel, audio: np.ndarray) -> dict[str, Any]:
    segments, _ = aligner.transcribe(
        audio,
        language="de",
        beam_size=1,
        temperature=0.0,
        condition_on_previous_text=False,
        word_timestamps=True,
        vad_filter=False,
    )
    segments = list(segments)
    words = [word for segment in segments for word in (segment.words or [])]
    return {
        "text": " ".join(segment.text.strip() for segment in segments).strip(),
        "words": [
            {"word": word.word.strip(), "start": round(word.start, 3), "end": round(word.end, 3)}
            for word in words
        ],
    }


def run(model: Any, aligner: WhisperModel, conditioning: tuple[Any, Any], variant: str, seed: int, output: Path, language: str = "de") -> dict[str, Any]:
    text = VARIANTS[variant]
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.cuda.synchronize()
    started = time.perf_counter()
    arrivals: list[float] = []
    chunks: list[np.ndarray] = []
    for tensor in model.inference_stream(
        text,
        language,
        *conditioning,
        stream_chunk_size=CHUNK_TOKENS,
        overlap_wav_len=1024,
        do_sample=True,
        **PARAMETERS,
    ):
        torch.cuda.synchronize()
        arrivals.append(time.perf_counter() - started)
        chunks.append(tensor.detach().float().cpu().numpy())
    total = time.perf_counter() - started
    audio = np.concatenate(chunks) if chunks else np.zeros(0, np.float32)
    duration = len(audio) / RATE
    target = output / f"{variant}--seed-{seed}.wav"
    sf.write(target, audio, RATE, subtype="PCM_16")
    segments, _ = aligner.transcribe(audio, language=language, beam_size=1, temperature=0.0, condition_on_previous_text=False, word_timestamps=True, vad_filter=False)
    segments = list(segments)
    words = [word for segment in segments for word in (segment.words or [])]
    probe = {"text": " ".join(segment.text.strip() for segment in segments).strip(), "words": [{"word": word.word.strip(), "start": round(word.start, 3), "end": round(word.end, 3)} for word in words]}
    activity_end = active_end(audio)
    expected_words = norm(text).split()
    observed_words = norm(probe["text"]).split()
    prefix_exact = observed_words[: len(expected_words)] == expected_words
    no_extra_words = len(observed_words) == len(expected_words)
    expected_word_end = probe["words"][len(expected_words) - 1]["end"] if prefix_exact and len(probe["words"]) >= len(expected_words) else None
    active_tail = max(0.0, activity_end - expected_word_end) if expected_word_end is not None else None
    clean_eos = bool(prefix_exact and no_extra_words and active_tail is not None and active_tail <= 0.60)
    durations = [len(chunk) / RATE for chunk in chunks]
    result = {
        "variant": variant,
        "text": text,
        "seed": seed,
        "wav": str(target),
        "audioDurationSeconds": round(duration, 6),
        "estimatedAudioCodes": int(np.ceil(len(audio) / 1024)),
        "ttfaSeconds": round(arrivals[0], 6),
        "totalGenerationSeconds": round(total, 6),
        "rtf": round(total / duration, 6),
        "transcript": probe["text"],
        "transcriptWords": probe["words"],
        "activeEndSeconds": activity_end,
        "expectedWordEndSeconds": expected_word_end,
        "activeTailSeconds": round(active_tail, 6) if active_tail is not None else None,
        "cleanEos": clean_eos,
        **playback(arrivals, durations),
    }
    print(f"{variant} seed={seed} clean={clean_eos} duration={duration:.3f}s ttfa={result['ttfaSeconds']:.3f}s rtf={result['rtf']:.3f}", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/training/xtts-v2-short-punctuation-matrix"))
    args = parser.parse_args()
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("Velora F reference checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=True)
    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    model = runtime.synthesizer.tts_model
    conditioning = model.get_conditioning_latents(audio_path=[str(REFERENCE)])
    aligner = WhisperModel("small", device="cpu", compute_type="int8")
    list(model.inference_stream("Systemstart.", "de", *conditioning, stream_chunk_size=CHUNK_TOKENS, **PARAMETERS))
    runs = [run(model, aligner, conditioning, variant, seed, args.output) for variant in VARIANTS for seed in SEEDS]
    summaries = {}
    for variant in VARIANTS:
        items = [item for item in runs if item["variant"] == variant]
        summaries[variant] = {
            "cleanEos": sum(item["cleanEos"] for item in items),
            "runs": len(items),
            "ttfaP95Seconds": round(float(np.percentile([item["ttfaSeconds"] for item in items], 95)), 6),
            "rtfMax": max(item["rtf"] for item in items),
            "underruns": sum(item["underruns"] for item in items),
        }
    result = {
        "referenceSha256": REFERENCE_SHA256,
        "seeds": SEEDS,
        "variants": VARIANTS,
        "normalisationCases": {raw: {"input": value, "normalized": normalize_input(value)} for raw, value in NORMALISATION_CASES.items()},
        "cleanEosDefinition": "exact normalized ASR words and <=0.60 s >=-40 dBFS activity after the expected final word",
        "runs": runs,
        "summary": summaries,
    }
    (args.output / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

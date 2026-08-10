"""Hybrid proof: native XTTS for normal text, VAD-only stop for very short text."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from faster_whisper import WhisperModel
from TTS.api import TTS

BASE_PATH = Path(__file__).with_name("xtts_short_punctuation_matrix.py")
SPEC = importlib.util.spec_from_file_location("punctuation", BASE_PATH)
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

SEEDS = tuple(range(70_001, 70_021))


def first_terminal_pause(audio: np.ndarray) -> int | None:
    frame = round(0.02 * base.RATE)
    rms = np.asarray([np.sqrt(np.mean(audio[i : i + frame] ** 2)) for i in range(0, len(audio), frame)])
    active = rms >= 10 ** (-40 / 20)
    active_indexes = np.flatnonzero(active)
    if not len(active_indexes) or (active_indexes[-1] + 1) * 0.02 < 0.45:
        return None
    for index in range(max(active_indexes[0] + 1, 22), len(active) - 14):
        if active[:index].any() and not active[index : index + 15].any():
            return min(len(audio), round((index * 0.02 + 0.20) * base.RATE))
    return None


def run(model, aligner, conditioning, seed: int, output: Path) -> dict:
    text = base.VARIANTS["period"]
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.cuda.synchronize()
    started = time.perf_counter()
    generator = model.inference_stream(text, "de", *conditioning, stream_chunk_size=base.CHUNK_TOKENS, overlap_wav_len=1024, do_sample=True, **base.PARAMETERS)
    chunks = []
    arrivals = []
    cutoff = None
    try:
        for tensor in generator:
            torch.cuda.synchronize()
            arrivals.append(time.perf_counter() - started)
            chunks.append(tensor.detach().float().cpu().numpy())
            cumulative = np.concatenate(chunks)
            cutoff = first_terminal_pause(cumulative)
            if cutoff is not None:
                break
    finally:
        generator.close()
    total = time.perf_counter() - started
    generated = np.concatenate(chunks) if chunks else np.zeros(0, np.float32)
    playable = generated[:cutoff] if cutoff is not None else generated
    target = output / f"short-de--seed-{seed}.wav"
    sf.write(target, playable, base.RATE, subtype="PCM_16")
    probe = base.transcribe(aligner, playable)
    clean = base.norm(probe["text"]) == base.norm(text)
    duration = len(playable) / base.RATE
    # The decisive chunk is trimmed before release; earlier chunks retain their arrival.
    release_lengths = [len(chunk) for chunk in chunks]
    if cutoff is not None:
        excess = len(generated) - cutoff
        release_lengths[-1] = max(0, release_lengths[-1] - excess)
    nonempty = [(at, length) for at, length in zip(arrivals, release_lengths, strict=True) if length]
    result = {
        "seed": seed,
        "text": text,
        "wav": str(target),
        "decision": "first 300 ms pause after >=450 ms active speech; retain 200 ms silence",
        "vadDecision": cutoff is not None,
        "generatedAudioSeconds": round(len(generated) / base.RATE, 6),
        "audioDurationSeconds": round(duration, 6),
        "ttfaSeconds": round(nonempty[0][0], 6),
        "totalGenerationSeconds": round(total, 6),
        "rtf": round(total / duration, 6),
        "transcript": probe["text"],
        "clean": clean,
        **base.playback([item[0] for item in nonempty], [item[1] / base.RATE for item in nonempty]),
    }
    print(f"seed={seed} clean={clean} decision={result['vadDecision']} duration={duration:.3f}s ttfa={result['ttfaSeconds']:.3f}s rtf={result['rtf']:.3f} underruns={result['underruns']}", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/mnt/e/Kyrion/Data/voice-training/xtts-v2-short-vad-hybrid"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if hashlib.sha256(base.REFERENCE.read_bytes()).hexdigest() != base.REFERENCE_SHA256:
        raise RuntimeError("reference checksum mismatch")
    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    model = runtime.synthesizer.tts_model
    conditioning = model.get_conditioning_latents(audio_path=[str(base.REFERENCE)])
    aligner = WhisperModel("small", device="cpu", compute_type="int8")
    list(model.inference_stream("Systemstart.", "de", *conditioning, stream_chunk_size=base.CHUNK_TOKENS, **base.PARAMETERS))
    runs = [run(model, aligner, conditioning, seed, args.output) for seed in SEEDS]
    summary = {
        "clean": sum(item["clean"] for item in runs),
        "runs": len(runs),
        "ttfaP95Seconds": round(float(np.percentile([item["ttfaSeconds"] for item in runs], 95)), 6),
        "rtfMax": max(item["rtf"] for item in runs),
        "underruns": sum(item["underruns"] for item in runs),
        "allVadDecisions": all(item["vadDecision"] for item in runs),
    }
    (args.output / "results.json").write_text(json.dumps({"routing": "apply only to empirically short text; all other text remains native 20-token XTTS", "runs": runs, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

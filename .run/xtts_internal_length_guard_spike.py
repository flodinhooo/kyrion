"""Public max_new_tokens XTTS runaway-bound spike."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import torch
from TTS.api import TTS

BASE_PATH = Path(__file__).with_name("xtts_live_generator_guard_spike.py")
SPEC = importlib.util.spec_from_file_location("xtts_live_base", BASE_PATH)
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def run(model, conditioning, text_id: str, run_index: int, output: Path) -> dict:
    language, text = base.TEXTS[text_id]
    max_codes = max(48, 14 * len(base.norm(text).split()))
    torch.manual_seed(50_000 + run_index)
    torch.cuda.manual_seed_all(50_000 + run_index)
    started = time.perf_counter()
    arrivals = []
    chunks = []
    original_limit = model.gpt.max_gen_mel_tokens
    model.gpt.max_gen_mel_tokens = max_codes
    try:
        for tensor in model.inference_stream(
            text,
            language,
            *conditioning,
            stream_chunk_size=base.CHUNK_TOKENS,
            overlap_wav_len=1024,
            do_sample=True,
            **base.PARAMETERS,
        ):
            torch.cuda.synchronize()
            arrivals.append(time.perf_counter() - started)
            chunks.append(tensor.detach().float().cpu().numpy())
    finally:
        model.gpt.max_gen_mel_tokens = original_limit
    total = time.perf_counter() - started
    audio = np.concatenate(chunks)
    duration = len(audio) / base.RATE
    releases = [
        {"atSeconds": at, "samples": len(chunk)}
        for at, chunk in zip(arrivals, chunks, strict=True)
    ]
    target = output / f"{text_id}--run-{run_index}.wav"
    base.write_wav(target, audio)
    result = {
        "textId": text_id,
        "text": text,
        "run": run_index,
        "maxNewTokens": max_codes,
        "limitMechanism": "internal model.gpt.max_gen_mel_tokens (not public/stable)",
        "maximumCodeAudioSeconds": round(max_codes * 1024 / base.RATE, 6),
        "wav": str(target),
        "audioDurationSeconds": round(duration, 6),
        "chunks": len(chunks),
        "ttfaSeconds": round(arrivals[0], 6),
        "totalSeconds": round(total, 6),
        "rtf": round(total / duration, 6),
        "postDecisionReleasedSeconds": 0.0,
        **base.playback(releases),
    }
    print(
        f"{text_id} run={run_index} cap={max_codes} duration={duration:.3f}s ttfa={result['ttfaSeconds']:.3f}s rtf={result['rtf']:.3f} underruns={result['underruns']}",
        flush=True,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/training/xtts-v2-internal-length-guard")
    )
    args = parser.parse_args()
    if hashlib.sha256(base.REFERENCE.read_bytes()).hexdigest() != base.REFERENCE_SHA256:
        raise RuntimeError("reference checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=True)
    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    model = runtime.synthesizer.tts_model
    conditioning = model.get_conditioning_latents(audio_path=[str(base.REFERENCE)])
    list(
        model.inference_stream(
            "Systemstart.",
            "de",
            *conditioning,
            stream_chunk_size=base.CHUNK_TOKENS,
            **base.PARAMETERS,
        )
    )
    runs = []
    for index in range(1, 11):
        runs.append(run(model, conditioning, "short-de", index, args.output))
    for text_id in base.TEXTS:
        if text_id != "short-de":
            runs.append(run(model, conditioning, text_id, 1, args.output))
    (args.output / "results.json").write_text(
        json.dumps(
            {"formula": "max(48, 14 * normalized_word_count)", "runs": runs},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

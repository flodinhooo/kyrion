"""Reproducible isolated TTS benchmark for Velora's immutable F profile.

Run this script inside the provider-specific WSL virtual environment. It does
not alter the production provider configuration or canonical reference audio.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path
from typing import Any

import soundfile as sf
import torch


ROOT = Path("/mnt/e/dev/Kyrion/kyrion")
REFERENCE = ROOT / ".run/velora-female-options/F_weiblich_klar.wav"
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
TRANSCRIPT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
    "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)
TEXTS = {
    "short": "Ich bin Velora.",
    "medium": "Ich bin Velora und begleite dich durch deinen Alltag.",
    "long": (
        "Natürlich, Flo. Ich helfe dir dabei, den Überblick zu behalten und die nächsten "
        "Schritte in Ruhe zu planen. Sag mir einfach, womit wir beginnen sollen."
    ),
}


def synchronize() -> None:
    torch.cuda.synchronize()


def gpu_memory() -> dict[str, float]:
    return {
        "allocatedMiB": round(torch.cuda.memory_allocated() / 1024**2, 3),
        "reservedMiB": round(torch.cuda.memory_reserved() / 1024**2, 3),
        "peakAllocatedMiB": round(torch.cuda.max_memory_allocated() / 1024**2, 3),
    }


def process_peak_rss_mib() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 3)


def verify_reference() -> None:
    actual = hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
    if actual != REFERENCE_SHA256:
        raise RuntimeError(f"Reference checksum mismatch: {actual}")


def qwen_benchmark(
    model_path: str,
    output: Path,
    dtype_name: str,
    sampling: bool,
) -> dict[str, Any]:
    from qwen_tts import Qwen3TTSModel

    torch.cuda.reset_peak_memory_stats()
    synchronize()
    started = time.perf_counter()
    dtype = {"float16": torch.float16, "float32": torch.float32}[dtype_name]
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map="cuda:0",
        dtype=dtype,
        attn_implementation="sdpa",
    )
    synchronize()
    load_seconds = time.perf_counter() - started
    permanent_after_load = gpu_memory()

    started = time.perf_counter()
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(REFERENCE),
        ref_text=TRANSCRIPT,
        x_vector_only_mode=False,
    )
    synchronize()
    conditioning_seconds = time.perf_counter() - started
    permanent_after_conditioning = gpu_memory()

    results: dict[str, Any] = {}
    for text_id, text in TEXTS.items():
        runs = []
        for run_index in range(4):
            torch.manual_seed(42 + run_index)
            torch.cuda.manual_seed_all(42 + run_index)
            decode_seconds = 0.0
            original_decode = model.model.speech_tokenizer.decode

            def measured_decode(*args: Any, **kwargs: Any) -> Any:
                nonlocal decode_seconds
                synchronize()
                decode_started = time.perf_counter()
                value = original_decode(*args, **kwargs)
                synchronize()
                decode_seconds += time.perf_counter() - decode_started
                return value

            model.model.speech_tokenizer.decode = measured_decode
            torch.cuda.reset_peak_memory_stats()
            synchronize()
            run_started = time.perf_counter()
            wavs, sample_rate = model.generate_voice_clone(
                text=text,
                language="German",
                voice_clone_prompt=prompt,
                do_sample=sampling,
                temperature=0.9,
                top_k=50,
                top_p=1.0,
                repetition_penalty=1.05,
                subtalker_dosample=sampling,
                subtalker_temperature=0.9,
                subtalker_top_k=50,
                subtalker_top_p=1.0,
                max_new_tokens=2048,
            )
            synchronize()
            generation_seconds = time.perf_counter() - run_started
            model.model.speech_tokenizer.decode = original_decode
            audio_duration = len(wavs[0]) / sample_rate
            if run_index == 1:
                sf.write(output / f"{text_id}.wav", wavs[0], sample_rate)
            runs.append(
                {
                    "kind": "first" if run_index == 0 else f"warm-{run_index}",
                    "generationSeconds": round(generation_seconds, 6),
                    "audioDecodeSeconds": round(decode_seconds, 6),
                    "codeGenerationAndOverheadSeconds": round(
                        generation_seconds - decode_seconds, 6
                    ),
                    "audioDurationSeconds": round(audio_duration, 6),
                    "rtf": round(generation_seconds / audio_duration, 6),
                    "vram": gpu_memory(),
                    "processPeakRssMiB": process_peak_rss_mib(),
                }
            )
        warm = [item["generationSeconds"] for item in runs[1:]]
        results[text_id] = {
            "text": text,
            "runs": runs,
            "warmMeanSeconds": round(sum(warm) / len(warm), 6),
            "warmMinSeconds": min(warm),
        }

    return {
        "provider": "qwen3-tts",
        "model": model_path,
        "device": torch.cuda.get_device_name(0),
        "dtype": dtype_name,
        "samplingEnabled": sampling,
        "attentionImplementation": "sdpa",
        "modelLoadSeconds": round(load_seconds, 6),
        "voiceConditioningSeconds": round(conditioning_seconds, 6),
        "permanentVramAfterLoad": permanent_after_load,
        "permanentVramAfterConditioning": permanent_after_conditioning,
        "processPeakRssMiB": process_peak_rss_mib(),
        "tests": results,
    }


def chatterbox_benchmark(output: Path) -> dict[str, Any]:
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    torch.cuda.reset_peak_memory_stats()
    synchronize()
    started = time.perf_counter()
    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    synchronize()
    load_seconds = time.perf_counter() - started
    permanent_after_load = gpu_memory()

    started = time.perf_counter()
    model.prepare_conditionals(str(REFERENCE), exaggeration=0.45)
    synchronize()
    conditioning_seconds = time.perf_counter() - started
    permanent_after_conditioning = gpu_memory()

    results: dict[str, Any] = {}
    for text_id, text in TEXTS.items():
        runs = []
        for run_index in range(4):
            torch.manual_seed(42 + run_index)
            torch.cuda.manual_seed_all(42 + run_index)
            torch.cuda.reset_peak_memory_stats()
            synchronize()
            run_started = time.perf_counter()
            wav = model.generate(
                text,
                language_id="de",
                cfg_weight=0.5,
                temperature=0.65,
                repetition_penalty=2.0,
            )
            synchronize()
            generation_seconds = time.perf_counter() - run_started
            audio = wav.squeeze(0).cpu().numpy()
            audio_duration = len(audio) / model.sr
            if run_index == 1:
                sf.write(output / f"{text_id}.wav", audio, model.sr)
            runs.append(
                {
                    "kind": "first" if run_index == 0 else f"warm-{run_index}",
                    "generationSeconds": round(generation_seconds, 6),
                    "audioDecodeSeconds": None,
                    "audioDurationSeconds": round(audio_duration, 6),
                    "rtf": round(generation_seconds / audio_duration, 6),
                    "vram": gpu_memory(),
                    "processPeakRssMiB": process_peak_rss_mib(),
                }
            )
        warm = [item["generationSeconds"] for item in runs[1:]]
        results[text_id] = {
            "text": text,
            "runs": runs,
            "warmMeanSeconds": round(sum(warm) / len(warm), 6),
            "warmMinSeconds": min(warm),
        }

    return {
        "provider": "chatterbox-multilingual",
        "model": "ChatterboxMultilingualTTS",
        "device": torch.cuda.get_device_name(0),
        "modelLoadSeconds": round(load_seconds, 6),
        "voiceConditioningSeconds": round(conditioning_seconds, 6),
        "permanentVramAfterLoad": permanent_after_load,
        "permanentVramAfterConditioning": permanent_after_conditioning,
        "processPeakRssMiB": process_peak_rss_mib(),
        "tests": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("qwen", "chatterbox"), required=True)
    parser.add_argument("--model")
    parser.add_argument("--label", required=True)
    parser.add_argument("--dtype", choices=("float16", "float32"), default="float16")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--output-root", default=str(ROOT / "voice-benchmark/raw"))
    args = parser.parse_args()

    verify_reference()
    output = Path(args.output_root) / args.label
    output.mkdir(parents=True, exist_ok=True)
    if args.provider == "qwen":
        if not args.model:
            parser.error("--model is required for Qwen")
        result = qwen_benchmark(
            args.model,
            output,
            args.dtype,
            not args.deterministic,
        )
    else:
        result = chatterbox_benchmark(output)
    result["referenceSha256"] = REFERENCE_SHA256
    result["benchmarkTexts"] = TEXTS
    result["note"] = (
        "The first run per text is the first sample for that text length. Only the first "
        "text also follows a freshly loaded and conditioned model. Public provider APIs "
        "return complete audio; generationSeconds is not true streaming TTFA."
    )
    target = output / "metrics.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()

"""Isolated staged benchmark for local dynamic Short-TTS candidates.

Run in the provider-specific environment. This runner writes private WAVs and
JSON metrics outside Git and never imports Kyrion production provider code.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import wave
from ctypes import Structure, byref, c_size_t, c_ulong, c_void_p, sizeof
from pathlib import Path
from typing import Any

import numpy as np

ROOT_WINDOWS = Path("E:/dev/Kyrion/kyrion")
ROOT_WSL = Path("/mnt/e/dev/Kyrion/kyrion")
ROOT = ROOT_WSL if ROOT_WSL.exists() else ROOT_WINDOWS
CORPUS = ROOT / ".run/short_tts_corpus.json"
REFERENCE = ROOT / ".run/velora-female-options/F_weiblich_klar.wav"
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
REFERENCE_TRANSCRIPT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
    "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)
PIPER_MODEL = Path(
    "E:/Kyrion/Data/models/piper/de_DE-kerstin-low/de/de_DE/kerstin/low/"
    "de_DE-kerstin-low.onnx"
)
SEEDS = (71_001, 71_002, 71_003)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def process_rss_mib() -> float:
    if sys.platform == "win32":
        class ProcessMemoryCounters(Structure):
            _fields_ = [
                ("cb", c_ulong),
                ("PageFaultCount", c_ulong),
                ("PeakWorkingSetSize", c_size_t),
                ("WorkingSetSize", c_size_t),
                ("QuotaPeakPagedPoolUsage", c_size_t),
                ("QuotaPagedPoolUsage", c_size_t),
                ("QuotaPeakNonPagedPoolUsage", c_size_t),
                ("QuotaNonPagedPoolUsage", c_size_t),
                ("PagefileUsage", c_size_t),
                ("PeakPagefileUsage", c_size_t),
                ("PrivateUsage", c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = sizeof(counters)
        handle = c_void_p(ctypes.windll.kernel32.GetCurrentProcess())
        if not ctypes.windll.psapi.GetProcessMemoryInfo(handle, byref(counters), counters.cb):
            raise OSError("GetProcessMemoryInfo failed")
        return round(counters.WorkingSetSize / 1024**2, 3)
    page_size = os.sysconf("SC_PAGE_SIZE")
    resident_pages = int(Path("/proc/self/statm").read_text().split()[1])
    return round(resident_pages * page_size / 1024**2, 3)


def total_ram_mib() -> float:
    if sys.platform == "win32":
        class MemoryStatus(Structure):
            _fields_ = [
                ("dwLength", c_ulong),
                ("dwMemoryLoad", c_ulong),
                ("ullTotalPhys", c_size_t),
                ("ullAvailPhys", c_size_t),
                ("ullTotalPageFile", c_size_t),
                ("ullAvailPageFile", c_size_t),
                ("ullTotalVirtual", c_size_t),
                ("ullAvailVirtual", c_size_t),
                ("ullAvailExtendedVirtual", c_size_t),
            ]

        status = MemoryStatus()
        status.dwLength = sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return round(status.ullTotalPhys / 1024**2, 3)
    pages = os.sysconf("SC_PHYS_PAGES")
    return round(pages * os.sysconf("SC_PAGE_SIZE") / 1024**2, 3)


def process_metrics(started_cpu: float, started_wall: float) -> dict[str, float]:
    cpu_seconds = time.process_time() - started_cpu
    wall = max(time.perf_counter() - started_wall, 1e-9)
    return {
        "processCpuSeconds": round(cpu_seconds, 6),
        "processCpuPercentOfOneCore": round(100.0 * cpu_seconds / wall, 3),
        "processRssMiB": process_rss_mib(),
    }


def wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    import io

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        pcm = (np.clip(samples, -1.0, 1.0) * 32_767).astype("<i2").tobytes()
        target.writeframes(pcm)
    return buffer.getvalue()


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> bytes:
    data = wav_bytes(samples, sample_rate)
    path.write_bytes(data)
    return data


def runtime_context() -> dict[str, Any]:
    gpu = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "logicalCpuCount": os.cpu_count(),
        "totalRamMiB": total_ram_mib(),
        "gpu": gpu.stdout.strip() or None,
    }


def benchmark_chatterbox(cases: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    torch.cuda.synchronize()
    load_started = time.perf_counter()
    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - load_started
    conditioning_started = time.perf_counter()
    model.prepare_conditionals(str(REFERENCE), exaggeration=0.45)
    torch.cuda.synchronize()
    conditioning_seconds = time.perf_counter() - conditioning_started
    model.generate("Systemstart.", language_id="de", cfg_weight=0.5, temperature=0.65)
    torch.cuda.synchronize()

    runs = []
    for case in cases:
        for run_index in range(case["runs"]):
            seed = SEEDS[run_index]
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            torch.cuda.reset_peak_memory_stats()
            cpu_started = time.process_time()
            started = time.perf_counter()
            wav = model.generate(
                case["text"],
                language_id=case["locale"],
                cfg_weight=0.5,
                temperature=0.65,
                repetition_penalty=2.0,
            )
            torch.cuda.synchronize()
            total = time.perf_counter() - started
            audio = wav.squeeze(0).detach().float().cpu().numpy()
            filename = f"{case['id']}--seed-{seed}.wav"
            data = write_wav(output / filename, audio, model.sr)
            duration = len(audio) / model.sr
            runs.append(
                {
                    "caseId": case["id"],
                    "stage": case["stage"],
                    "locale": case["locale"],
                    "category": case["category"],
                    "text": case["text"],
                    "runIndex": run_index,
                    "seed": seed,
                    "wav": filename,
                    "wavSha256": sha256_bytes(data),
                    "sampleRate": model.sr,
                    "audioDurationSeconds": round(duration, 6),
                    "firstPlayableAudioSeconds": round(total, 6),
                    "firstPlayableDefinition": "batch API completion; no PCM is exposed earlier",
                    "totalSynthesisSeconds": round(total, 6),
                    "rtf": round(total / duration, 6),
                    "streaming": False,
                    "gpuPeakAllocatedMiB": round(
                        torch.cuda.max_memory_allocated() / 1024**2, 3
                    ),
                    **process_metrics(cpu_started, started),
                    "classification": "pending_manual_review",
                    "review": {},
                }
            )
            print(f"chatterbox {case['id']} seed={seed} total={total:.3f}s", flush=True)
    return {
        "engine": "chatterbox-tts",
        "engineVersion": "0.1.7",
        "model": "ChatterboxMultilingualTTS",
        "configuration": {
            "cfgWeight": 0.5,
            "temperature": 0.65,
            "repetitionPenalty": 2.0,
            "referenceSha256": REFERENCE_SHA256,
            "referenceTranscript": REFERENCE_TRANSCRIPT,
        },
        "modelLoadSeconds": round(load_seconds, 6),
        "conditioningSeconds": round(conditioning_seconds, 6),
        "runs": runs,
    }


def benchmark_piper(cases: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    from piper import PiperVoice

    load_started = time.perf_counter()
    voice = PiperVoice.load(PIPER_MODEL, use_cuda=False)
    load_seconds = time.perf_counter() - load_started
    runs = []
    for case in cases:
        if case["locale"] != "de":
            continue
        for run_index in range(case["runs"]):
            seed = SEEDS[run_index]
            cpu_started = time.process_time()
            started = time.perf_counter()
            chunks = []
            first_audio = None
            sample_rate = voice.config.sample_rate
            for chunk in voice.synthesize(case["text"]):
                if first_audio is None:
                    first_audio = time.perf_counter() - started
                chunks.append(np.frombuffer(chunk.audio_int16_bytes, dtype="<i2"))
            total = time.perf_counter() - started
            pcm = np.concatenate(chunks) if chunks else np.zeros(0, dtype="<i2")
            audio = pcm.astype(np.float32) / 32_767.0
            filename = f"{case['id']}--seed-{seed}.wav"
            data = write_wav(output / filename, audio, sample_rate)
            duration = len(audio) / sample_rate
            runs.append(
                {
                    "caseId": case["id"],
                    "stage": case["stage"],
                    "locale": case["locale"],
                    "category": case["category"],
                    "text": case["text"],
                    "runIndex": run_index,
                    "seed": seed,
                    "seedSupported": False,
                    "wav": filename,
                    "wavSha256": sha256_bytes(data),
                    "sampleRate": sample_rate,
                    "audioDurationSeconds": round(duration, 6),
                    "firstPlayableAudioSeconds": round(first_audio or total, 6),
                    "firstPlayableDefinition": "first AudioChunk yielded by PiperVoice.synthesize",
                    "totalSynthesisSeconds": round(total, 6),
                    "rtf": round(total / duration, 6),
                    "streaming": True,
                    "gpuPeakAllocatedMiB": None,
                    **process_metrics(cpu_started, started),
                    "classification": "pending_manual_review",
                    "review": {},
                }
            )
            print(f"piper {case['id']} run={run_index} total={total:.3f}s", flush=True)
    return {
        "engine": "piper-tts",
        "engineVersion": "1.6.0",
        "model": "de_DE-kerstin-low",
        "configuration": {
            "device": "cpu",
            "modelSha256": hashlib.sha256(PIPER_MODEL.read_bytes()).hexdigest(),
            "modelCard": "CC0 dataset; piper1-gpl runtime GPL-3.0-or-later",
        },
        "modelLoadSeconds": round(load_seconds, 6),
        "conditioningSeconds": 0.0,
        "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("chatterbox", "piper"), required=True)
    parser.add_argument("--stage", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases = [case for case in corpus["cases"] if case["stage"] == args.stage]
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("Velora F reference checksum mismatch")
    output = args.output_root / args.provider / f"stage-{args.stage}"
    output.mkdir(parents=True, exist_ok=True)
    result = (
        benchmark_chatterbox(cases, output)
        if args.provider == "chatterbox"
        else benchmark_piper(cases, output)
    )
    result.update(
        {
            "benchmarkStage": args.stage,
            "corpusSchemaVersion": corpus["schemaVersion"],
            "corpusSha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
            "runtime": runtime_context(),
            "manualReviewStatus": "pending_manual_review",
            "reviewDimensions": [
                "clean_or_hallucinated_or_truncated",
                "semantic_completion",
                "extra_speech",
                "de_pronunciation",
                "en_pronunciation",
                "names_and_numbers",
                "velora_voice_identity",
                "prosody_and_naturalness",
            ],
        }
    )
    (output / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(output / "results.json")


if __name__ == "__main__":
    main()

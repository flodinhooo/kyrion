"""Bounded offline TTS comparison; never changes application/provider configuration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import wave
from pathlib import Path

CASES = {
    "short": "Die Luft streut blaues Licht besonders stark.",
    "two": "Ein See ist ein stehendes Gewässer. Ein Fluss transportiert Wasser durch die Landschaft.",
    "list": "1. Drehe den Wasserhahn beim Zähneputzen ab.\n2. Nutze Waschmaschine und Geschirrspüler nur voll beladen.\n3. Sammle Regenwasser für den Garten.",
}


def wav_info(path: Path) -> dict:
    with wave.open(str(path)) as audio:
        frames = audio.getnframes()
        expected = frames * audio.getnchannels() * audio.getsampwidth()
        if frames <= 0 or len(audio.readframes(frames)) != expected:
            raise ValueError("EMPTY_OR_TRUNCATED_WAV")
        return {
            "audioSeconds": frames / audio.getframerate(),
            "sampleRate": audio.getframerate(),
            "channels": audio.getnchannels(),
            "sampleWidth": audio.getsampwidth(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }


def rss_kib(pid: int) -> int:
    try:
        line = next(
            line
            for line in Path(f"/proc/{pid}/status").read_text().splitlines()
            if line.startswith("VmRSS:")
        )
        return int(line.split()[1])
    except (FileNotFoundError, StopIteration):
        return 0


def gpu_state() -> str:
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def require_memory() -> None:
    available = next(
        line
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    if int(available.split()[1]) < 8 * 1024 * 1024:
        raise RuntimeError("INSUFFICIENT_MEMORY_FOR_ISOLATED_EXPERIMENT")


def no_network() -> None:
    def forbidden(*_args, **_kwargs):
        raise RuntimeError("EXPERIMENT_NETWORK_DISABLED")

    socket.create_connection = forbidden
    socket.getaddrinfo = forbidden
    socket.socket.connect = forbidden
    socket.socket.connect_ex = forbidden


def summarize(rows: list[dict]) -> dict:
    summary = {}
    for case in CASES:
        warm = [row for row in rows if row["case"] == case and row["phase"] == "warm"]
        if len(warm) != 3:
            raise ValueError("EXACTLY_THREE_WARM_RUNS_REQUIRED")
        times = [row["firstPlayableSeconds"] for row in warm]
        summary[case] = {
            "medianFirstPlayableSeconds": statistics.median(times),
            "minFirstPlayableSeconds": min(times),
            "maxFirstPlayableSeconds": max(times),
            "medianRtf": statistics.median(row["rtf"] for row in warm),
            "audioSeconds": [row["audioSeconds"] for row in warm],
        }
    return summary


def main(args) -> None:
    import resource

    require_memory()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "engine": args.engine,
        "texts": CASES,
        "warmRunsPerText": 3,
        "clock": time.get_clock_info("perf_counter").implementation,
        "gpuBefore": gpu_state(),
        "streamingOutput": False,
        "coldBaselineCaveat": "Active Chatterbox was deliberately not restarted; true engine-cold measurement is unavailable.",
    }
    startup = time.perf_counter()
    runtime = None
    if args.engine == "moss-cpu":
        for name in ["HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"]:
            os.environ[name] = "1"
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        for name in ["OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"]:
            os.environ[name] = "2"
        model_dir = args.moss_root / "models"
        for required in [
            "MOSS-TTS-Nano-100M-ONNX/browser_poc_manifest.json",
            "MOSS-TTS-Nano-100M-ONNX/moss_tts_global_shared.data",
            "MOSS-Audio-Tokenizer-Nano-ONNX/moss_audio_tokenizer_decode_shared.data",
        ]:
            if not (model_dir / required).is_file():
                raise RuntimeError("LOCAL_MODEL_ASSET_MISSING_NO_DOWNLOAD")
        no_network()
        sys.path.insert(0, str(args.moss_root))
        from onnx_tts_runtime import OnnxTtsRuntime

        runtime = OnnxTtsRuntime(
            model_dir=model_dir,
            thread_count=2,
            max_new_frames=375,
            do_sample=True,
            sample_mode="fixed",
            execution_provider="cpu",
            output_dir=output,
        )
        metadata.update(
            cpuThreads=2,
            frameBudget=375,
            providers=runtime.ort_providers,
            engineRevision=subprocess.run(
                ["git", "-C", str(args.moss_root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip(),
        )
        target = os.getpid()
    else:
        target = args.server_pid
        if (
            not target
            or "chatterbox_tts_server.py"
            not in Path(f"/proc/{target}/cmdline").read_text()
        ):
            raise RuntimeError("REVIEWED_CHATTERBOX_PID_REQUIRED")
    metadata["loadSeconds"] = time.perf_counter() - startup
    rows = []
    for case, text in CASES.items():
        for iteration in range(4):
            require_memory()
            phase = (
                "warm"
                if iteration
                else "cold_first_request"
                if not rows and runtime
                else "first_use_text"
            )
            path = output / f"{case}-{iteration}.wav"
            stop = threading.Event()
            samples = [rss_kib(target)]

            def sample(stop=stop, samples=samples):
                while not stop.wait(0.1):
                    samples.append(rss_kib(target))

            worker = threading.Thread(target=sample, daemon=True)
            worker.start()
            started = time.perf_counter()
            extra = {}
            try:
                if runtime is not None:
                    result = runtime.synthesize(
                        text=text,
                        prompt_audio_path=args.reference,
                        output_audio_path=path,
                        sample_mode="fixed",
                        do_sample=True,
                        streaming=True,
                        max_new_frames=375,
                        enable_wetext=True,
                        enable_normalize_tts_text=True,
                        seed=82000 + iteration,
                    )
                    extra = {
                        "textChunks": len(result["text_chunks"]),
                        "generatedFrames": len(result["audio_token_ids"]),
                        "frameBudgetReached": any(
                            len(chunk["generated_frames"]) >= 375
                            for chunk in result["chunk_results"]
                        ),
                    }
                else:
                    request = urllib.request.Request(
                        "http://127.0.0.1:8020/v1/synthesize",
                        data=json.dumps({"text": text, "voiceId": "velora"}).encode(),
                        headers={
                            "Content-Type": "application/json",
                            "X-Kyrion-Correlation-Id": str(uuid.uuid4()),
                        },
                    )
                    with urllib.request.urlopen(request, timeout=120) as response:
                        data = response.read(10_000_001)
                        if len(data) > 10_000_000:
                            raise ValueError("AUDIO_LIMIT_EXCEEDED")
                        path.write_bytes(data)
                        extra = {
                            "engineComputeMs": response.headers.get(
                                "X-Kyrion-Tts-Compute-Ms"
                            ),
                            "queueMs": response.headers.get("X-Kyrion-Tts-Queue-Ms"),
                        }
                info = wav_info(path)
                elapsed = time.perf_counter() - started
            finally:
                stop.set()
                worker.join(timeout=2)
            row = {
                "case": case,
                "phase": phase,
                "iteration": iteration,
                "characters": len(text),
                "firstPlayableSeconds": elapsed,
                "totalSeconds": elapsed,
                "rtf": elapsed / info["audioSeconds"],
                "rssPeakKiB": max(samples),
                "wav": path.name,
                "wavBytes": path.stat().st_size,
                **info,
                **extra,
            }
            rows.append(row)
            (output / "progress.json").write_text(
                json.dumps({"metadata": metadata, "runs": rows}, indent=2),
                encoding="utf-8",
            )
            print(json.dumps(row), flush=True)
    metadata["gpuAfter"] = gpu_state()
    metadata["clientPeakRssKiB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "metadata": metadata,
        "runs": rows,
        "summary": summarize(rows),
        "manualReview": "pending",
        "activeConfigurationChanged": False,
        "streamingNote": "Both public APIs expose complete WAV only; internal streaming decode is not playable delivery.",
    }
    (output / "results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"summary": result["summary"], "output": str(output)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--engine", choices=["moss-cpu", "chatterbox-http"], required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--server-pid", type=int)
    parser.add_argument(
        "--moss-root", type=Path, default=Path("/training/MOSS-TTS-Nano")
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(
            "/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav"
        ),
    )
    main(parser.parse_args())

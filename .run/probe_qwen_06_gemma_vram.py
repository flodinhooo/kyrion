"""Measure RTX 2070 residency with warm Gemma 1B and Qwen TTS 0.6B."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

import torch
from qwen_tts import Qwen3TTSModel


MODEL = "/training/models/qwen3-tts/voice-clone-base-0.6b"
REFERENCE = Path(
    "/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav"
)
TRANSCRIPT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
    "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)


def used_vram_mib() -> int:
    value = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=memory.used",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    return int(value.strip())


class PeakSampler:
    def __init__(self) -> None:
        self.values: list[int] = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self.stop.is_set():
            try:
                self.values.append(used_vram_mib())
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
            self.stop.wait(0.05)

    def __enter__(self) -> "PeakSampler":
        self.thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop.set()
        self.thread.join()

    @property
    def peak(self) -> int | None:
        return max(self.values) if self.values else None


def warm_gemma() -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(
        [
            "/mnt/e/Ollama/App/ollama.exe",
            "run",
            "gemma3:1b",
            "Antworte nur mit dem Wort bereit.",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "seconds": time.perf_counter() - started,
        "response": completed.stdout.strip(),
    }


def main() -> None:
    result: dict[str, object] = {"baselineVramMiB": used_vram_mib()}
    model = Qwen3TTSModel.from_pretrained(
        MODEL,
        device_map="cuda:0",
        dtype=torch.float32,
        attn_implementation="sdpa",
    )
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(REFERENCE), ref_text=TRANSCRIPT, x_vector_only_mode=False
    )
    torch.cuda.synchronize()
    result["qwenWarmIdleVramMiB"] = used_vram_mib()

    with PeakSampler() as sampler:
        result["gemma"] = warm_gemma()
    result["gemmaPeakVramMiB"] = sampler.peak
    result["bothWarmIdleVramMiB"] = used_vram_mib()

    with PeakSampler() as sampler:
        started = time.perf_counter()
        wavs, sample_rate = model.generate_voice_clone(
            text="Ich bin Velora und begleite dich durch deinen Alltag.",
            language="German",
            voice_clone_prompt=prompt,
            do_sample=True,
            temperature=0.9,
            top_k=50,
            top_p=1.0,
            repetition_penalty=1.05,
            subtalker_dosample=True,
            subtalker_temperature=0.9,
            subtalker_top_k=50,
            subtalker_top_p=1.0,
            max_new_tokens=2048,
        )
        torch.cuda.synchronize()
    result["ttsSeconds"] = time.perf_counter() - started
    result["ttsAudioSeconds"] = len(wavs[0]) / sample_rate
    result["ttsPeakVramMiB"] = sampler.peak
    result["finalBothWarmIdleVramMiB"] = used_vram_mib()
    result["totalVramMiB"] = torch.cuda.get_device_properties(0).total_memory // 1024**2
    result["remainingAtTtsPeakMiB"] = (
        result["totalVramMiB"] - result["ttsPeakVramMiB"]
        if result["ttsPeakVramMiB"] is not None
        else None
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

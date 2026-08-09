"""Isolated follow-up spike for Qwen 1.7B streaming chunk boundaries.

This imports the original spike helpers and changes only local chunk assembly.
No installed Qwen package or Kyrion production component is modified.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch


ROOT = Path("/mnt/e/dev/Kyrion/kyrion")
BASE_PATH = ROOT / ".run/qwen_17_streaming_spike.py"
SPEC = importlib.util.spec_from_file_location("qwen_streaming_base", BASE_PATH)
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = base
SPEC.loader.exec_module(base)


@dataclass(frozen=True)
class Strategy:
    name: str
    initial_frames: int
    stride_frames: int
    overlap_frames: int
    crossfade_ms: int = 0


STRATEGIES = (
    Strategy("fixed-5-context-25", 5, 5, 25),
    Strategy("fixed-5-context-50", 5, 5, 50),
    Strategy("start-5-then-20", 5, 20, 50),
    Strategy("start-5-then-20-xfade-40ms", 5, 20, 50, 40),
    Strategy("fixed-10-context-25", 10, 10, 25),
    Strategy("fixed-10-context-50", 10, 10, 50),
    Strategy("start-10-then-20", 10, 20, 50),
    Strategy("start-10-then-20-xfade-40ms", 10, 20, 50, 40),
)


@dataclass
class BoundaryDecoder:
    runtime: Any
    reference_codes: torch.Tensor
    strategy: Strategy
    started: float
    event_file: Path
    frames: list[torch.Tensor] = field(default_factory=list)
    chunks: list[np.ndarray] = field(default_factory=list)
    boundaries: list[int] = field(default_factory=list)
    pending_tail: np.ndarray | None = None
    decoded_until: int = 0
    first_playable_ms: float | None = None
    decode_seconds: float = 0.0
    decode_count: int = 0

    @property
    def fade_samples(self) -> int:
        return round(self.strategy.crossfade_ms * base.SAMPLE_RATE / 1_000)

    def event(self, name: str, **values: Any) -> None:
        base.write_event(
            self.event_file,
            {"event": name, "elapsedMs": base.now_ms(self.started), **values},
        )

    def on_frame(self, index: int, frame: torch.Tensor) -> None:
        self.frames.append(frame)
        count = len(self.frames)
        if count == 1:
            self.event("FIRST_CODEC_FRAME", frameIndex=index)
        if self.decoded_until == 0 and count == self.strategy.initial_frames:
            self._decode(count)
        elif self.decoded_until and count - self.decoded_until == self.strategy.stride_frames:
            self._decode(count)

    def _append(self, pcm: np.ndarray, reconstructed_tail: np.ndarray | None) -> None:
        fade = self.fade_samples
        if not fade:
            if self.chunks:
                self.boundaries.append(sum(map(len, self.chunks)))
            self.chunks.append(pcm)
            return

        if self.pending_tail is not None:
            assert reconstructed_tail is not None
            usable = min(fade, len(self.pending_tail), len(reconstructed_tail))
            ramp = np.linspace(0.0, 1.0, usable, endpoint=True, dtype=np.float32)
            blended = self.pending_tail[-usable:] * (1.0 - ramp) + reconstructed_tail[-usable:] * ramp
            self.boundaries.append(sum(map(len, self.chunks)))
            self.chunks.append(blended)
        if len(pcm) > fade:
            self.chunks.append(pcm[:-fade])
            self.pending_tail = pcm[-fade:].copy()
        else:
            self.pending_tail = pcm.copy()

    def _decode(self, end: int) -> None:
        first = self.decoded_until == 0
        new_count = end if first else end - self.decoded_until
        context_start = max(0, self.decoded_until - self.strategy.overlap_frames)
        generated = torch.stack(self.frames[context_start:end])
        if first:
            reference = self.reference_codes[-self.strategy.overlap_frames:].to(generated.device)
            context_frames = len(reference)
            codes = torch.cat([reference, generated])
        else:
            context_frames = self.decoded_until - context_start
            codes = generated
        self.event(
            "FIRST_DECODE_START" if first else f"CHUNK_{self.decode_count + 1}_START",
            frameEnd=end,
            contextFrames=context_frames,
            newFrames=new_count,
        )
        base.sync()
        decode_started = time.perf_counter()
        wav = base.decode_codes(self.runtime, codes)
        base.sync()
        elapsed = time.perf_counter() - decode_started
        self.decode_seconds += elapsed
        self.decode_count += 1
        cut = context_frames * base.SAMPLES_PER_FRAME
        reconstructed = wav[max(0, cut - self.fade_samples):cut] if not first and self.fade_samples else None
        new_pcm = wav[cut:cut + new_count * base.SAMPLES_PER_FRAME]
        self._append(new_pcm, reconstructed)
        self.decoded_until = end
        if first:
            self.first_playable_ms = base.now_ms(self.started)
            self.event("FIRST_PLAYABLE_PCM", samples=len(new_pcm), decodeMs=round(elapsed * 1_000, 3))
        else:
            self.event(f"CHUNK_{self.decode_count}", samples=len(new_pcm), decodeMs=round(elapsed * 1_000, 3))

    def finish(self) -> None:
        if len(self.frames) > self.decoded_until:
            self._decode(len(self.frames))
        if self.pending_tail is not None:
            self.chunks.append(self.pending_tail)
            self.pending_tail = None

    @property
    def audio(self) -> np.ndarray:
        return np.concatenate(self.chunks) if self.chunks else np.empty(0, dtype=np.float32)


def run(runtime: Any, prompt_items: list[Any], strategy: Strategy, run_index: int, output: Path) -> dict[str, Any]:
    run_dir = output / strategy.name / f"run-{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)
    events = run_dir / "events.jsonl"
    events.write_text("", encoding="utf-8")
    # The same seed per repetition makes strategies directly comparable.
    torch.manual_seed(1_700_000 + run_index)
    torch.cuda.manual_seed_all(1_700_000 + run_index)
    generation, reference_codes = base.prepare_generation(runtime, prompt_items, base.TEXTS["long"])
    started = time.perf_counter()
    base.write_event(events, {"event": "TTS_TEXT_AVAILABLE", "elapsedMs": 0.0})
    decoder = BoundaryDecoder(runtime, reference_codes, strategy, started, events)
    cancel = __import__("threading").Event()
    restore = base.install_frame_hook(runtime.model.talker, decoder.on_frame, cancel)
    torch.cuda.reset_peak_memory_stats()
    try:
        codes_list, _ = runtime.model.generate(**generation)
        base.sync()
        generation_complete_ms = base.now_ms(started)
    finally:
        restore()
    decoder.finish()
    control = base.full_decode(runtime, reference_codes, codes_list[0])
    streamed = decoder.audio
    sf.write(run_dir / "streaming.wav", streamed, base.SAMPLE_RATE)
    sf.write(run_dir / "full-decode.wav", control, base.SAMPLE_RATE)
    metrics = {
        "strategy": strategy.__dict__,
        "run": run_index,
        "firstPlayablePcmMs": decoder.first_playable_ms,
        "generationCompleteMs": generation_complete_ms,
        "decodeCount": decoder.decode_count,
        "decodeTotalSeconds": round(decoder.decode_seconds, 6),
        "memory": base.memory(),
        "quality": base.quality_metrics(streamed, control, decoder.boundaries),
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "voice-streaming-boundary-optimization")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if base.hashlib.sha256(base.REFERENCE.read_bytes()).hexdigest() != base.REFERENCE_SHA256:
        raise RuntimeError("Velora F reference checksum mismatch")
    runtime = base.Qwen3TTSModel.from_pretrained(
        base.MODEL_PATH, device_map="cuda:0", dtype=torch.float16, attn_implementation="sdpa"
    )
    prompt_items = runtime.create_voice_clone_prompt(
        ref_audio=str(base.REFERENCE), ref_text=base.TRANSCRIPT, x_vector_only_mode=False
    )
    prompt = runtime._prompt_items_to_voice_clone_prompt(prompt_items)
    base.decode_codes(runtime, prompt["ref_code"][0][-50:])
    runtime.generate_voice_clone(
        text="Systemstart.", language="German", voice_clone_prompt=prompt_items,
        do_sample=True, temperature=0.9, top_k=50, top_p=1.0,
        repetition_penalty=1.05, subtalker_dosample=True,
        subtalker_temperature=0.9, subtalker_top_k=50, subtalker_top_p=1.0,
        max_new_tokens=256,
    )
    base.sync()
    results = []
    for strategy in STRATEGIES:
        for run_index in range(1, args.runs + 1):
            result = run(runtime, prompt_items, strategy, run_index, args.output)
            results.append(result)
            print(strategy.name, run_index, result["firstPlayablePcmMs"], flush=True)
    (args.output / "summary.json").write_text(json.dumps({"runs": results}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

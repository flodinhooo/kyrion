"""Isolated Qwen3-TTS 1.7B codec-frame streaming proof of concept.

This script monkeypatches only the in-memory Qwen talker instance. It never
modifies the installed package or any Kyrion production service.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import resource
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


ROOT = Path("/mnt/e/dev/Kyrion/kyrion")
MODEL_PATH = "/training/models/qwen3-tts/voice-clone-base"
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
FRAME_WINDOWS = (5, 10, 15, 20, 25)
OVERLAP_FRAMES = 25
SAMPLE_RATE = 24_000
SAMPLES_PER_FRAME = 1_920


class GenerationCancelled(RuntimeError):
    pass


def sync() -> None:
    torch.cuda.synchronize()


def now_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1_000, 3)


def memory() -> dict[str, float]:
    return {
        "allocatedMiB": round(torch.cuda.memory_allocated() / 1024**2, 3),
        "reservedMiB": round(torch.cuda.memory_reserved() / 1024**2, 3),
        "peakAllocatedMiB": round(torch.cuda.max_memory_allocated() / 1024**2, 3),
        "processPeakRssMiB": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 3
        ),
    }


def write_event(target: Path, event: dict[str, Any]) -> None:
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def install_frame_hook(
    talker: Any,
    on_frame: Callable[[int, torch.Tensor], None],
    cancel: threading.Event,
) -> Callable[[], None]:
    original = talker.forward
    frame_index = 0

    @functools.wraps(original)
    def hooked(*args: Any, **kwargs: Any) -> Any:
        nonlocal frame_index
        if cancel.is_set():
            raise GenerationCancelled("generation cancelled")
        output = original(*args, **kwargs)
        codec_ids = output.hidden_states[1] if output.hidden_states else None
        if codec_ids is not None:
            frame = codec_ids[0].detach().clone()
            if frame.numel() != 16:
                raise RuntimeError(f"Expected 16 codec groups, got {frame.shape}")
            on_frame(frame_index, frame)
            frame_index += 1
        if cancel.is_set():
            raise GenerationCancelled("generation cancelled")
        return output

    talker.forward = hooked

    def restore() -> None:
        talker.forward = original

    return restore


def prepare_generation(
    runtime: Qwen3TTSModel,
    prompt_items: list[Any],
    text: str,
) -> tuple[dict[str, Any], torch.Tensor]:
    prompt = runtime._prompt_items_to_voice_clone_prompt(prompt_items)
    input_ids = runtime._tokenize_texts([runtime._build_assistant_text(text)])
    ref_text = prompt_items[0].ref_text
    ref_ids = [
        runtime._tokenize_texts([runtime._build_ref_text(ref_text)])[0]
        if ref_text
        else None
    ]
    kwargs = runtime._merge_generate_kwargs(
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
    return (
        {
            "input_ids": input_ids,
            "ref_ids": ref_ids,
            "voice_clone_prompt": prompt,
            "languages": ["German"],
            "non_streaming_mode": False,
            **kwargs,
        },
        prompt["ref_code"][0],
    )


def decode_codes(runtime: Qwen3TTSModel, codes: torch.Tensor) -> np.ndarray:
    wavs, _ = runtime.model.speech_tokenizer.decode([{"audio_codes": codes}])
    return wavs[0]


def full_decode(
    runtime: Qwen3TTSModel,
    reference_codes: torch.Tensor,
    generated_codes: torch.Tensor,
) -> np.ndarray:
    codes = torch.cat([reference_codes.to(generated_codes.device), generated_codes])
    wav = decode_codes(runtime, codes)
    cut = int(reference_codes.shape[0] / codes.shape[0] * wav.shape[0])
    return wav[cut:]


@dataclass
class StreamingDecoder:
    runtime: Qwen3TTSModel
    reference_codes: torch.Tensor
    window: int
    started: float
    event_file: Path
    chunk_dir: Path | None
    cancel: threading.Event
    frames: list[torch.Tensor] = field(default_factory=list)
    chunks: list[np.ndarray] = field(default_factory=list)
    boundaries: list[int] = field(default_factory=list)
    first_playable_ms: float | None = None
    decode_seconds: float = 0.0
    decode_count: int = 0

    def event(self, name: str, **values: Any) -> None:
        write_event(
            self.event_file,
            {"event": name, "elapsedMs": now_ms(self.started), **values},
        )

    def on_frame(self, index: int, frame: torch.Tensor) -> None:
        if self.cancel.is_set():
            raise GenerationCancelled("generation cancelled")
        self.frames.append(frame)
        count = len(self.frames)
        if count == 1:
            self.event("FIRST_CODEC_FRAME", frameIndex=index)
        if count in FRAME_WINDOWS:
            self.event(f"FRAME_{count}_READY", frameIndex=index)
        if count % self.window == 0:
            self._decode_new(count)

    def _decode_new(self, end: int) -> None:
        if self.cancel.is_set():
            raise GenerationCancelled("generation cancelled")
        first = not self.chunks
        start = 0 if first else max(0, end - self.window - OVERLAP_FRAMES)
        generated = torch.stack(self.frames[start:end])
        overlap = 0 if first else end - self.window - start
        if first:
            reference_context = self.reference_codes[-OVERLAP_FRAMES:].to(
                generated.device
            )
            overlap = reference_context.shape[0]
            codes = torch.cat([reference_context, generated])
        else:
            codes = generated
        self.event(
            "FIRST_DECODE_START" if first else f"CHUNK_{len(self.chunks) + 1}_START",
            frameEnd=end,
            overlapFrames=overlap,
        )
        sync()
        decode_started = time.perf_counter()
        wav = decode_codes(self.runtime, codes)
        sync()
        elapsed = time.perf_counter() - decode_started
        self.decode_seconds += elapsed
        self.decode_count += 1
        cut = overlap * SAMPLES_PER_FRAME
        new_pcm = wav[cut:]
        if not first:
            expected = self.window * SAMPLES_PER_FRAME
            new_pcm = new_pcm[-expected:]
        if self.chunks:
            self.boundaries.append(sum(len(chunk) for chunk in self.chunks))
        self.chunks.append(new_pcm)
        if self.chunk_dir is not None:
            self.chunk_dir.mkdir(parents=True, exist_ok=True)
            sf.write(
                self.chunk_dir / f"chunk-{len(self.chunks):03d}.wav",
                new_pcm,
                SAMPLE_RATE,
            )
        if first:
            self.first_playable_ms = now_ms(self.started)
            self.event(
                "FIRST_PLAYABLE_PCM",
                samples=len(new_pcm),
                decodeMs=round(elapsed * 1_000, 3),
            )
        else:
            self.event(
                f"CHUNK_{len(self.chunks)}",
                samples=len(new_pcm),
                decodeMs=round(elapsed * 1_000, 3),
            )

    def finish(self) -> None:
        remaining = len(self.frames) % self.window
        if remaining and not self.cancel.is_set():
            end = len(self.frames)
            original_window = self.window
            self.window = remaining
            try:
                self._decode_new(end)
            finally:
                self.window = original_window

    @property
    def audio(self) -> np.ndarray:
        return np.concatenate(self.chunks) if self.chunks else np.empty(0, dtype=np.float32)


def quality_metrics(streamed: np.ndarray, full: np.ndarray, boundaries: list[int]) -> dict[str, Any]:
    common = min(len(streamed), len(full))
    rmse = float(np.sqrt(np.mean((streamed[:common] - full[:common]) ** 2))) if common else None
    clicks = [
        {
            "sample": boundary,
            "absoluteJump": round(float(abs(streamed[boundary] - streamed[boundary - 1])), 6),
            "localRms": round(
                float(np.sqrt(np.mean(streamed[max(0, boundary - 240):boundary + 240] ** 2))),
                6,
            ),
        }
        for boundary in boundaries
        if 0 < boundary < len(streamed)
    ]
    return {
        "streamedSamples": len(streamed),
        "fullSamples": len(full),
        "lengthDeltaSamples": len(streamed) - len(full),
        "lengthDeltaMs": round((len(streamed) - len(full)) / SAMPLE_RATE * 1_000, 3),
        "alignedRmse": round(rmse, 6) if rmse is not None else None,
        "boundaryCount": len(boundaries),
        "maxBoundaryJump": max((item["absoluteJump"] for item in clicks), default=0.0),
        "boundaries": clicks,
    }


def run_streaming(
    runtime: Qwen3TTSModel,
    prompt_items: list[Any],
    text_id: str,
    window: int,
    run_index: int,
    output: Path,
) -> dict[str, Any]:
    run_dir = output / text_id / f"window-{window}" / f"run-{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)
    event_file = run_dir / "events.jsonl"
    event_file.write_text("", encoding="utf-8")
    torch.manual_seed(1_700_000 + run_index)
    torch.cuda.manual_seed_all(1_700_000 + run_index)
    generation, reference_codes = prepare_generation(runtime, prompt_items, TEXTS[text_id])
    cancel = threading.Event()
    started = time.perf_counter()
    write_event(event_file, {"event": "TTS_TEXT_AVAILABLE", "elapsedMs": 0.0})
    decoder = StreamingDecoder(
        runtime,
        reference_codes,
        window,
        started,
        event_file,
        run_dir / "chunks" if run_index == 1 else None,
        cancel,
    )
    restore = install_frame_hook(runtime.model.talker, decoder.on_frame, cancel)
    torch.cuda.reset_peak_memory_stats()
    try:
        codes_list, _ = runtime.model.generate(**generation)
        sync()
        generation_complete_ms = now_ms(started)
        decoder.event("GENERATION_COMPLETE", frames=len(decoder.frames))
    finally:
        restore()
    decoder.finish()
    generated = codes_list[0]
    control = full_decode(runtime, reference_codes, generated)
    streamed = decoder.audio
    if run_index == 1:
        sf.write(run_dir / "streaming.wav", streamed, SAMPLE_RATE)
        sf.write(run_dir / "full-decode.wav", control, SAMPLE_RATE)
    metrics = {
        "textId": text_id,
        "windowFrames": window,
        "run": run_index,
        "firstCodecFrameMs": next(
            json.loads(line)["elapsedMs"]
            for line in event_file.read_text(encoding="utf-8").splitlines()
            if json.loads(line)["event"] == "FIRST_CODEC_FRAME"
        ),
        "firstPlayablePcmMs": decoder.first_playable_ms,
        "generationCompleteMs": generation_complete_ms,
        "generatedFrames": len(decoder.frames),
        "audioDurationSeconds": round(len(control) / SAMPLE_RATE, 6),
        "rtf": round(generation_complete_ms / 1_000 / (len(control) / SAMPLE_RATE), 6),
        "decodeTotalSeconds": round(decoder.decode_seconds, 6),
        "decodeCount": decoder.decode_count,
        "memory": memory(),
        "quality": quality_metrics(streamed, control, decoder.boundaries),
    }
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metrics


def run_cancellation(
    runtime: Qwen3TTSModel,
    prompt_items: list[Any],
    cancel_after_ms: int,
    run_index: int,
    output: Path,
) -> dict[str, Any]:
    run_dir = output / "cancellation" / f"cancel-{cancel_after_ms}ms" / f"run-{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)
    event_file = run_dir / "events.jsonl"
    event_file.write_text("", encoding="utf-8")
    generation, reference_codes = prepare_generation(runtime, prompt_items, TEXTS["long"])
    cancel = threading.Event()
    started = time.perf_counter()
    write_event(event_file, {"event": "TTS_TEXT_AVAILABLE", "elapsedMs": 0.0})
    decoder = StreamingDecoder(
        runtime, reference_codes, 5, started, event_file, None, cancel
    )
    restore = install_frame_hook(runtime.model.talker, decoder.on_frame, cancel)

    def request_cancel() -> None:
        time.sleep(cancel_after_ms / 1_000)
        write_event(
            event_file,
            {"event": "CANCEL_REQUESTED", "elapsedMs": now_ms(started)},
        )
        cancel.set()

    timer = threading.Thread(target=request_cancel, daemon=True)
    timer.start()
    stopped_ms: float | None = None
    caught = False
    torch.cuda.reset_peak_memory_stats()
    try:
        runtime.model.generate(**generation)
    except GenerationCancelled:
        sync()
        stopped_ms = now_ms(started)
        caught = True
        write_event(event_file, {"event": "GENERATION_STOPPED", "elapsedMs": stopped_ms})
    finally:
        restore()
        timer.join()
    requested = next(
        json.loads(line)["elapsedMs"]
        for line in event_file.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["event"] == "CANCEL_REQUESTED"
    )
    metrics = {
        "cancelAfterMs": cancel_after_ms,
        "run": run_index,
        "cancelCaught": caught,
        "cancelRequestedMs": requested,
        "generationStoppedMs": stopped_ms,
        "cancelToStopMs": round(stopped_ms - requested, 3) if stopped_ms else None,
        "framesProduced": len(decoder.frames),
        "chunksWritten": len(decoder.chunks),
        "memoryAfterCancellation": memory(),
    }
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "voice-streaming-spike"
    )
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("Velora F reference checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=True)

    load_started = time.perf_counter()
    runtime = Qwen3TTSModel.from_pretrained(
        MODEL_PATH,
        device_map="cuda:0",
        dtype=torch.float16,
        attn_implementation="sdpa",
    )
    sync()
    model_load_seconds = time.perf_counter() - load_started
    conditioning_started = time.perf_counter()
    prompt_items = runtime.create_voice_clone_prompt(
        ref_audio=str(REFERENCE), ref_text=TRANSCRIPT, x_vector_only_mode=False
    )
    sync()
    conditioning_seconds = time.perf_counter() - conditioning_started
    # Compile/warm the codec decoder outside measured runs, matching a
    # permanently warm voice runtime rather than charging CUDA first-use work
    # to FIRST_PLAYABLE_PCM.
    prompt_dict = runtime._prompt_items_to_voice_clone_prompt(prompt_items)
    decode_codes(runtime, prompt_dict["ref_code"][0][-OVERLAP_FRAMES:])
    sync()
    runtime.generate_voice_clone(
        text="Systemstart.",
        language="German",
        voice_clone_prompt=prompt_items,
        do_sample=True,
        temperature=0.9,
        top_k=50,
        top_p=1.0,
        repetition_penalty=1.05,
        subtalker_dosample=True,
        subtalker_temperature=0.9,
        subtalker_top_k=50,
        subtalker_top_p=1.0,
        max_new_tokens=256,
    )
    sync()

    if args.smoke:
        result = run_streaming(runtime, prompt_items, "short", 5, 1, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    all_results = []
    for text_id in TEXTS:
        for window in FRAME_WINDOWS:
            for run_index in range(1, 4):
                result = run_streaming(
                    runtime, prompt_items, text_id, window, run_index, args.output
                )
                all_results.append(result)
                print(
                    f"{text_id=} {window=} {run_index=} "
                    f"first_pcm_ms={result['firstPlayablePcmMs']}",
                    flush=True,
                )

    cancellations = []
    for cancel_after_ms in (500, 1000, 2000):
        for run_index in range(1, 4):
            cancellations.append(
                run_cancellation(
                    runtime, prompt_items, cancel_after_ms, run_index, args.output
                )
            )

    summary = {
        "model": "Qwen3-TTS-12Hz-1.7B-Base",
        "dtype": "float16",
        "attentionImplementation": "sdpa",
        "referenceSha256": REFERENCE_SHA256,
        "modelLoadSeconds": round(model_load_seconds, 6),
        "conditioningSeconds": round(conditioning_seconds, 6),
        "warmIdleMemory": memory(),
        "overlapFrames": OVERLAP_FRAMES,
        "runs": all_results,
        "cancellations": cancellations,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

"""VAD-gated and incremental-tail live guard comparison for XTTS v2."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import queue
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from faster_whisper import WhisperModel
from TTS.api import TTS

BASE_PATH = Path(__file__).with_name("xtts_live_generator_guard_spike.py")
SPEC = importlib.util.spec_from_file_location("xtts_live_base", BASE_PATH)
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

STRATEGIES = {
    "vad-small-cumulative": {"model": "small", "tail": False},
    "vad-small-tail": {"model": "small", "tail": True},
    "vad-tiny-tail": {"model": "tiny", "tail": True},
}


def new_pause(audio: np.ndarray, scanned_until: int) -> tuple[float, int] | None:
    frame = round(0.02 * base.RATE)
    rms = np.array(
        [
            np.sqrt(np.mean(audio[index : index + frame] ** 2))
            for index in range(0, len(audio), frame)
            if len(audio[index : index + frame])
        ]
    )
    quiet = rms < 10 ** (-40 / 20)
    begin = max(0, scanned_until // frame - 14)
    for index in range(begin, len(quiet) - 14):
        if quiet[index : index + 15].all() and (index + 15) * frame > scanned_until:
            return (index * 0.02, (index + 15) * frame)
    return None


def run(
    model: Any,
    aligner: WhisperModel,
    conditioning: tuple[Any, Any],
    strategy_name: str,
    text_id: str,
    run_index: int,
    output: Path,
) -> dict[str, Any]:
    strategy = STRATEGIES[strategy_name]
    language, text = base.TEXTS[text_id]
    expected_tokens = base.norm(text).split()
    torch.manual_seed(40_000 + run_index)
    torch.cuda.manual_seed_all(40_000 + run_index)
    started = time.perf_counter()
    cancel = threading.Event()
    done = threading.Event()
    items: queue.Queue[Any] = queue.Queue(maxsize=1)
    generated_events = []

    def produce() -> None:
        generator = model.inference_stream(
            text,
            language,
            *conditioning,
            stream_chunk_size=base.CHUNK_TOKENS,
            overlap_wav_len=1024,
            do_sample=True,
            **base.PARAMETERS,
        )
        try:
            for index, tensor in enumerate(generator):
                torch.cuda.synchronize()
                audio = tensor.detach().float().cpu().numpy()
                event = {
                    "index": index,
                    "atSeconds": time.perf_counter() - started,
                    "samples": len(audio),
                    "afterDecision": cancel.is_set(),
                }
                generated_events.append(event)
                if cancel.is_set():
                    break
                items.put((index, event["atSeconds"], audio))
        finally:
            generator.close()
            items.put(None)
            done.set()

    thread = threading.Thread(target=produce, daemon=True)
    thread.start()
    cumulative = np.zeros(0, np.float32)
    released = 0
    releases = []
    checks = []
    scanned_until = 0
    confirmed_tokens = 0
    confirmed_audio_end = 0.0
    decision = None
    match_time = None
    cutoff_samples = None
    pending_end = 0
    while True:
        item = items.get()
        if item is None:
            break
        chunk_index, _, chunk = item
        cumulative = np.concatenate((cumulative, chunk))
        pending_end = len(cumulative)
        pause = new_pause(cumulative, scanned_until)
        scanned_until = len(cumulative)
        if pause is None:
            now = time.perf_counter() - started
            releases.append({"atSeconds": now, "samples": len(cumulative) - released})
            released = len(cumulative)
            continue

        tail_start = max(0.0, confirmed_audio_end - 0.4) if strategy["tail"] else 0.0
        start_sample = round(tail_start * base.RATE)
        check_audio = base.resample_16k(cumulative[start_sample:])
        check_started = time.perf_counter()
        segments, _ = aligner.transcribe(
            check_audio,
            language=language,
            beam_size=1,
            temperature=0.0,
            condition_on_previous_text=False,
            word_timestamps=True,
            vad_filter=False,
        )
        words = [word for segment in segments for word in segment.words]
        observed = base.norm(" ".join(word.word.strip() for word in words)).split()
        expected_start = max(0, confirmed_tokens - 2) if strategy["tail"] else 0
        compare_count = min(len(observed), len(expected_tokens) - expected_start)
        expected_part = " ".join(
            expected_tokens[expected_start : expected_start + compare_count]
        )
        observed_part = " ".join(observed[:compare_count])
        score = (
            base.SequenceMatcher(None, expected_part, observed_part).ratio()
            if compare_count
            else 0.0
        )
        if compare_count and score >= 0.65:
            confirmed_tokens = max(confirmed_tokens, expected_start + compare_count)
            confirmed_audio_end = tail_start + words[compare_count - 1].end
        matched = confirmed_tokens >= len(expected_tokens)
        completed = time.perf_counter() - started
        if matched and match_time is None:
            match_time = completed
        cutoff = (
            base.silence_cutoff(cumulative, confirmed_audio_end) if matched else None
        )
        checks.append(
            {
                "chunk": chunk_index,
                "latencySeconds": round(time.perf_counter() - check_started, 6),
                "completedSeconds": round(completed, 6),
                "tailStartSeconds": round(tail_start, 6),
                "checkedAudioSeconds": round(len(check_audio) / 16_000, 6),
                "confirmedTokens": confirmed_tokens,
                "targetTokens": len(expected_tokens),
                "alignmentScore": round(score, 4),
                "cutoffSeconds": cutoff,
            }
        )
        if cutoff is not None:
            cutoff_samples = min(round(cutoff * base.RATE), len(cumulative))
            decision = time.perf_counter() - started
            cancel.set()
            if cutoff_samples > released:
                releases.append(
                    {"atSeconds": decision, "samples": cutoff_samples - released}
                )
                released = cutoff_samples
            break
        now = time.perf_counter() - started
        releases.append({"atSeconds": now, "samples": len(cumulative) - released})
        released = len(cumulative)

    if decision is None and pending_end > released:
        releases.append(
            {
                "atSeconds": time.perf_counter() - started,
                "samples": pending_end - released,
            }
        )
        released = pending_end
    if decision is not None:
        while not done.is_set():
            try:
                items.get(timeout=0.1)
            except queue.Empty:
                pass
    thread.join()
    cancellation = time.perf_counter() - started if decision else None
    playable = cumulative[:released]
    duration = len(playable) / base.RATE
    total = time.perf_counter() - started
    target = output / f"{strategy_name}--{text_id}--run-{run_index}.wav"
    base.write_wav(target, playable)
    result = {
        "strategy": strategy_name,
        "alignmentModel": strategy["model"],
        "incrementalTail": strategy["tail"],
        "textId": text_id,
        "text": text,
        "run": run_index,
        "wav": str(target),
        "asrCalls": len(checks),
        "checks": checks,
        "asrLatencyMedianSeconds": round(
            float(np.median([c["latencySeconds"] for c in checks])), 6
        )
        if checks
        else 0.0,
        "asrLatencyP95Seconds": round(
            float(np.percentile([c["latencySeconds"] for c in checks], 95)), 6
        )
        if checks
        else 0.0,
        "contentMatchSeconds": round(match_time, 6) if match_time else None,
        "guardDecisionSeconds": round(decision, 6) if decision else None,
        "generatorCancellationSeconds": round(cancellation, 6)
        if cancellation
        else None,
        "generatedPcmSeconds": round(
            sum(event["samples"] for event in generated_events) / base.RATE, 6
        ),
        "playableReleasedSeconds": round(duration, 6),
        "postDecisionGeneratedSeconds": round(
            sum(
                event["samples"] for event in generated_events if event["afterDecision"]
            )
            / base.RATE,
            6,
        ),
        "postDecisionReleasedSeconds": 0.0,
        "totalSeconds": round(total, 6),
        "rtf": round(total / duration, 6),
        **base.playback(releases),
    }
    print(
        f"{strategy_name} {text_id} run={run_index} calls={len(checks)} decision={result['guardDecisionSeconds']} ttfa={result['ttfaSeconds']} rtf={result['rtf']:.3f} underruns={result['underruns']}",
        flush=True,
    )
    return result


def save(output: Path, runs: list[dict[str, Any]]) -> None:
    (output / "results.json").write_text(
        json.dumps(
            {"strategies": STRATEGIES, "runs": runs}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/training/xtts-v2-live-guard-optimization")
    )
    args = parser.parse_args()
    if hashlib.sha256(base.REFERENCE.read_bytes()).hexdigest() != base.REFERENCE_SHA256:
        raise RuntimeError("reference checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=True)
    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    model = runtime.synthesizer.tts_model
    conditioning = model.get_conditioning_latents(audio_path=[str(base.REFERENCE)])
    aligners = {
        name: WhisperModel(name, device="cpu", compute_type="int8")
        for name in {item["model"] for item in STRATEGIES.values()}
    }
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
    for strategy, config in STRATEGIES.items():
        for index in range(1, 7):
            runs.append(
                run(
                    model,
                    aligners[config["model"]],
                    conditioning,
                    strategy,
                    "short-de",
                    index,
                    args.output,
                )
            )
            save(args.output, runs)
        for text_id in base.TEXTS:
            if text_id != "short-de":
                runs.append(
                    run(
                        model,
                        aligners[config["model"]],
                        conditioning,
                        strategy,
                        text_id,
                        1,
                        args.output,
                    )
                )
                save(args.output, runs)


if __name__ == "__main__":
    main()

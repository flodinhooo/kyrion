"""Record XTTS-v2 audio EOS evidence without modifying the installed runtime.

This runner is deliberately isolated from Kyrion services.  It attaches a
reversible Hugging Face ``LogitsProcessor`` to the installed XTTS generator,
records the effective sampling distribution for every audio code, and writes
listening WAVs plus JSON evidence outside Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch
from faster_whisper import WhisperModel
from transformers import LogitsProcessor, LogitsProcessorList
from TTS.api import TTS

ROOT = Path("/mnt/e/dev/Kyrion/kyrion")
REFERENCE = ROOT / ".run/velora-female-options/F_weiblich_klar.wav"
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
SAMPLE_RATE = 24_000
TOP_K = 10
SHORT_SEEDS = tuple(range(50_001, 50_011))
CONTROLS = {
    "medium-de": "Guten Morgen. Die Verbindung steht und alle lokalen Dienste sind bereit.",
    "long-de": (
        "Guten Morgen. Die Verbindung steht und alle lokalen Dienste sind bereit. "
        "Ich kann dir den aktuellen Zustand zusammenfassen und danach auf deinen "
        "nächsten Auftrag warten."
    ),
}
TERMINAL_TEXTS = {mark: f"Ich bin Velora{mark}" for mark in ".!?;"}
PARAMETERS = {
    "temperature": 0.75,
    "top_k": 50,
    "top_p": 0.85,
    "repetition_penalty": 10.0,
}


def _top_k_top_p(scores: torch.Tensor, top_k: int, top_p: float) -> torch.Tensor:
    """Apply XTTS's sampling warpers to one post-processor score vector."""
    filtered = scores.clone()
    if top_k > 0:
        threshold = torch.topk(filtered, min(top_k, filtered.numel())).values[-1]
        filtered[filtered < threshold] = -math.inf
    if 0.0 < top_p < 1.0:
        sorted_scores, sorted_indices = torch.sort(filtered, descending=True)
        cumulative = torch.softmax(sorted_scores, dim=-1).cumsum(dim=-1)
        remove = cumulative > top_p
        remove[1:] = remove[:-1].clone()
        remove[0] = False
        filtered[sorted_indices[remove]] = -math.inf
    return filtered


class EosTraceProcessor(LogitsProcessor):
    """Observe scores after built-in processors and before sampling warpers."""

    def __init__(self, prefix_length: int, started: float, eos_token_id: int) -> None:
        self.prefix_length = prefix_length
        self.started = started
        self.eos_token_id = eos_token_id
        self.records: list[dict[str, Any]] = []
        self._pending_probabilities: torch.Tensor | None = None

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
        adjusted = scores[0].detach().float() / PARAMETERS["temperature"]
        processed_probabilities = torch.softmax(adjusted, dim=-1)
        distribution = _top_k_top_p(adjusted, PARAMETERS["top_k"], PARAMETERS["top_p"])
        probabilities = torch.softmax(distribution, dim=-1)
        self._pending_probabilities = probabilities.detach().cpu()
        eos_probability = float(processed_probabilities[self.eos_token_id].item())
        eos_sampling_probability = float(probabilities[self.eos_token_id].item())
        eos_rank = int((adjusted > adjusted[self.eos_token_id]).sum().item()) + 1
        values, indices = torch.topk(probabilities, min(TOP_K, probabilities.numel()))
        self.records.append(
            {
                "position": int(input_ids.shape[-1] - self.prefix_length),
                "elapsedSeconds": round(time.perf_counter() - self.started, 6),
                "estimatedAudioSeconds": round(
                    max(0, input_ids.shape[-1] - self.prefix_length) * 1_024 / SAMPLE_RATE, 6
                ),
                "eosProbability": eos_probability,
                "eosSamplingProbability": eos_sampling_probability,
                "eosRank": eos_rank,
                "selectedTokenId": None,
                "selectedProbability": None,
                "eosSamplingSelectedMargin": None,
                "topTokens": [
                    {"tokenId": int(token), "probability": float(probability)}
                    for token, probability in zip(indices.tolist(), values.tolist(), strict=True)
                ],
            }
        )
        return scores

    def select(self, token: Any) -> None:
        selected = int(token.detach().reshape(-1)[0].item())
        record = self.records[-1]
        assert self._pending_probabilities is not None
        selected_probability = float(self._pending_probabilities[selected].item())
        self._pending_probabilities = None
        record["selectedTokenId"] = selected
        record["selectedProbability"] = selected_probability
        record["eosSamplingSelectedMargin"] = (
            record["eosSamplingProbability"] - selected_probability
        )


def tokenisation(model: Any, text: str, language: str) -> dict[str, Any]:
    stripped = text.strip().lower()
    preprocessed = model.tokenizer.preprocess_text(stripped, language)
    token_ids = model.tokenizer.encode(stripped, lang=language)
    return {
        "original": text,
        "strippedLower": stripped,
        "unicodeCodepoints": [f"U+{ord(character):04X}" for character in stripped],
        "preprocessed": preprocessed,
        "tokenIds": token_ids,
        "tokenCount": len(token_ids),
        "startTextTokenId": int(model.gpt.start_text_token),
        "stopTextTokenId": int(model.gpt.stop_text_token),
        "effectiveTokenIds": [int(model.gpt.start_text_token), *token_ids, int(model.gpt.stop_text_token)],
    }


def transcribe(aligner: WhisperModel, audio: np.ndarray, language: str) -> str:
    segments, _ = aligner.transcribe(
        audio,
        language=language,
        beam_size=1,
        temperature=0.0,
        condition_on_previous_text=False,
        vad_filter=False,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def run(
    model: Any,
    aligner: WhisperModel,
    conditioning: tuple[Any, Any],
    case_id: str,
    text: str,
    seed: int,
    output: Path,
) -> dict[str, Any]:
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.cuda.synchronize()
    started = time.perf_counter()
    trace: EosTraceProcessor | None = None
    original_get_generator = model.gpt.get_generator
    text_details = tokenisation(model, text, "de")

    def traced_generator(fake_inputs: torch.Tensor, **kwargs: Any) -> Any:
        nonlocal trace
        trace = EosTraceProcessor(
            fake_inputs.shape[-1], started, int(model.gpt.stop_audio_token)
        )
        processors = LogitsProcessorList(kwargs.pop("logits_processor", []))
        processors.append(trace)
        generator = original_get_generator(fake_inputs, logits_processor=processors, **kwargs)
        for token, latent in generator:
            trace.select(token)
            yield token, latent

    model.gpt.get_generator = traced_generator
    try:
        chunks = [
            tensor.detach().float().cpu().numpy()
            for tensor in model.inference_stream(
                text,
                "de",
                *conditioning,
                stream_chunk_size=20,
                overlap_wav_len=1_024,
                do_sample=True,
                **PARAMETERS,
            )
        ]
        torch.cuda.synchronize()
    finally:
        model.gpt.get_generator = original_get_generator

    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    duration = len(audio) / SAMPLE_RATE
    target = output / f"{case_id}--seed-{seed}.wav"
    sf.write(target, audio, SAMPLE_RATE, subtype="PCM_16")
    transcript = transcribe(aligner, audio, "de")
    assert trace is not None
    eos_token_id = int(model.gpt.stop_audio_token)
    eos_records = [item for item in trace.records if item["selectedTokenId"] == eos_token_id]
    result = {
        "caseId": case_id,
        "seed": seed,
        "text": text,
        "tokenisation": text_details,
        "audioDurationSeconds": round(duration, 6),
        "generationSeconds": round(time.perf_counter() - started, 6),
        "transcript": transcript,
        "classification": "unreviewed",
        "wav": str(target),
        "generatedCodeCount": len(trace.records),
        "nativeEosSelected": bool(eos_records),
        "trace": trace.records,
    }
    print(
        f"{case_id} seed={seed} codes={len(trace.records)} eos={bool(eos_records)} "
        f"audio={duration:.3f}s transcript={transcript!r}",
        flush=True,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/training/xtts-v2-eos-trace")
    )
    parser.add_argument("--short-runs", type=int, default=10, choices=range(1, 11))
    parser.add_argument("--skip-controls", action="store_true")
    args = parser.parse_args()
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("Velora F reference checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=True)

    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    model = runtime.synthesizer.tts_model
    conditioning = model.get_conditioning_latents(audio_path=[str(REFERENCE)])
    aligner = WhisperModel("small", device="cpu", compute_type="int8")
    list(model.inference_stream("Systemstart.", "de", *conditioning, stream_chunk_size=20))

    runs = [
        run(model, aligner, conditioning, "short-period-de", "Ich bin Velora.", seed, args.output)
        for seed in SHORT_SEEDS[: args.short_runs]
    ]
    if not args.skip_controls:
        runs.extend(
            run(model, aligner, conditioning, case_id, text, 60_001, args.output)
            for case_id, text in CONTROLS.items()
        )
    result = {
        "purpose": "isolated XTTS EOS/logit and text-tokenisation evidence",
        "referenceSha256": REFERENCE_SHA256,
        "eosTokenId": int(model.gpt.stop_audio_token),
        "audioTokenCount": int(model.gpt.num_audio_tokens),
        "samplingParameters": PARAMETERS,
        "terminalTokenisation": {
            mark: tokenisation(model, text, "de") for mark, text in TERMINAL_TEXTS.items()
        },
        "probabilityStage": (
            "eosProbability/rank are after built-in processors and temperature; "
            "eosSamplingProbability is additionally after reconstructed top-k/top-p warpers"
        ),
        "classificationInstructions": "Set each run classification to clean, hallucinated, or truncated after listening review.",
        "runs": runs,
    }
    (args.output / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

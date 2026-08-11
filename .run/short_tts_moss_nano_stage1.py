from __future__ import annotations

import hashlib
import json
import platform
import resource
import sys
import time
import wave
from pathlib import Path


REPO = Path("/training/MOSS-TTS-Nano")
MODEL_DIR = REPO / "models"
REFERENCE = Path(
    "/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav"
)
OUTPUT_DIR = Path(
    "/mnt/e/Kyrion/Data/voice-training/short-tts-provider-benchmark/"
    "moss-tts-nano/stage-1"
)

CASES = (
    ("de.identity", "Ich bin Velora.", 72001),
    ("de.identity", "Ich bin Velora.", 72002),
    ("de.identity", "Ich bin Velora.", 72003),
    ("de.acknowledge", "Alles klar.", 72001),
    ("de.reject", "Nein, das kann ich nicht.", 72001),
    ("de.greeting", "Guten Morgen, Flo.", 72001),
    ("de.domain", "Die Desk Lamp im Gamingraum ist eingeschaltet.", 72001),
)


def wav_metadata(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as wav_file:
        frame_count = wav_file.getnframes()
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width_bytes = wav_file.getsampwidth()
    return {
        "sampleRateHz": sample_rate,
        "channels": channels,
        "sampleWidthBytes": sample_width_bytes,
        "frameCount": frame_count,
        "audioDurationSeconds": frame_count / sample_rate,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> None:
    sys.path.insert(0, str(REPO))
    from onnx_tts_runtime import OnnxTtsRuntime

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    load_started = time.perf_counter()
    runtime = OnnxTtsRuntime(
        model_dir=MODEL_DIR,
        thread_count=4,
        max_new_frames=375,
        do_sample=True,
        sample_mode="fixed",
        execution_provider="cpu",
    )
    model_load_seconds = time.perf_counter() - load_started

    runs: list[dict[str, object]] = []
    for case_id, text, seed in CASES:
        output_path = OUTPUT_DIR / f"{case_id}--seed-{seed}.wav"
        started = time.perf_counter()
        result = runtime.synthesize(
            text=text,
            prompt_audio_path=REFERENCE,
            output_audio_path=output_path,
            sample_mode="fixed",
            do_sample=True,
            streaming=True,
            max_new_frames=375,
            enable_wetext=True,
            enable_normalize_tts_text=True,
            seed=seed,
        )
        synthesis_seconds = time.perf_counter() - started
        wav = wav_metadata(output_path)
        duration = float(wav["audioDurationSeconds"])
        runs.append(
            {
                "caseId": case_id,
                "language": "de",
                "input": text,
                "seed": seed,
                "wav": output_path.name,
                "synthesisSeconds": synthesis_seconds,
                "rtf": synthesis_seconds / duration,
                "firstPlayableAudioSeconds": None,
                "firstPlayableAudioNote": (
                    "Official CLI/runtime returns the waveform only after synthesis; "
                    "internal streaming codec decode is not an exposed playable stream."
                ),
                "classification": "pending_manual_review",
                "semanticCompletion": "pending_manual_review",
                "additionalSpeech": "pending_manual_review",
                "truncation": "pending_manual_review",
                "voiceIdentity": "pending_manual_review",
                "pronunciation": "pending_manual_review",
                "generatedAudioFrames": int(result["audio_token_ids"].shape[0]),
                **wav,
            }
        )

    result_document = {
        "schemaVersion": 1,
        "engine": "MOSS-TTS-Nano",
        "model": "OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX",
        "codec": "OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX",
        "engineRevision": "cc7bdf19c7639c0870dab22045a33b442760f6be",
        "license": "Apache-2.0 (official repository and model metadata)",
        "stage": 1,
        "candidateDecision": "B",
        "stage2Eligible": False,
        "stage2Gate": "owner manual review required",
        "manualReviewStatus": "pending_manual_review",
        "acceptedShortTtsProvider": None,
        "configuration": {
            "executionProvider": "cpu",
            "cpuThreads": 4,
            "sampleMode": "fixed",
            "doSample": True,
            "realtimeStreamingDecode": True,
            "maxNewFrames": 375,
            "referenceAudio": str(REFERENCE),
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "modelLoadSeconds": model_load_seconds,
            "peakResidentSetKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "warmState": "single persistent process after one model load",
        },
        "limitations": [
            "No ASR was used; all content and quality labels await owner listening.",
            "TTFA is not measurable through the official batch-returning Python API.",
            "Internal streaming codec decode does not by itself expose playable chunks.",
        ],
        "runs": runs,
    }
    (OUTPUT_DIR / "results.json").write_text(
        json.dumps(result_document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result_document, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

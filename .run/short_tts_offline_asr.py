"""Add non-authoritative whole-WAV ASR hints to Short-TTS benchmark outputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from faster_whisper import WhisperModel


def normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9äöüß]+", value.casefold()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    model = WhisperModel("small", device="cpu", compute_type="int8")
    results = []
    for provider in ("piper", "chatterbox"):
        source = args.root / provider / "stage-1/results.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        for run in data["runs"]:
            wav = source.parent / run["wav"]
            segments, _ = model.transcribe(
                str(wav),
                language=run["locale"],
                beam_size=1,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=False,
            )
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
            expected = normalize(run["text"])
            observed = normalize(transcript)
            results.append(
                {
                    "provider": provider,
                    "caseId": run["caseId"],
                    "seed": run["seed"],
                    "wav": str(wav),
                    "expected": run["text"],
                    "transcript": transcript,
                    "exactNormalizedMatch": observed == expected,
                    "expectedPrefix": observed.startswith(expected),
                    "extraNormalizedText": (
                        observed[len(expected) :].strip() if observed.startswith(expected) else None
                    ),
                    "authority": "offline_asr_hint_only_pending_manual_review",
                }
            )
            print(f"{provider} {run['caseId']} {run['seed']}: {transcript!r}", flush=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

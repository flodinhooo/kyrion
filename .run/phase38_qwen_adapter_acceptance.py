from __future__ import annotations

import json
import sys
import threading
import time
import wave
from dataclasses import asdict
from itertools import pairwise
from pathlib import Path
from threading import Event
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).parents[1] / "services" / "ai" / "src"))

from kyrion_ai.providers.qwen_streaming_tts import QwenStreamingTtsAdapter
from kyrion_ai.streaming_tts import StreamingTtsRequest, ValidatedStreamingTts

BASE_URL = "http://127.0.0.1:8030"
OUTPUT = Path("E:/Kyrion/Data/voice-training/phase38-qwen-adapter")
PHRASES = [
    ("de", "Velora, schalte bitte die desk lamp im Gamingraum ein."),
    ("en", "Velora, turn on the desk lamp in the gaming room, please."),
    (
        "de",
        "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste.",
    ),
]


def synthesize(adapter: ValidatedStreamingTts, index: int, locale: str, text: str) -> dict:
    started = time.perf_counter()
    first_audio = None
    chunk_times = []
    pcm = bytearray()
    request = StreamingTtsRequest(uuid4(), text, locale, "velora-f", index, True)
    events = []
    for event in adapter.stream(request, Event()):
        events.append(event)
        if event.type == "audio":
            now = time.perf_counter()
            first_audio = first_audio or now
            chunk_times.append(now)
            pcm.extend(event.pcm)
    elapsed = time.perf_counter() - started
    target = OUTPUT / f"phrase-{index + 1}-{locale}.wav"
    with wave.open(str(target), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24_000)
        output.writeframes(pcm)
    intervals = [right - left for left, right in pairwise(chunk_times)]
    return {
        "text": text,
        "wav": str(target),
        "firstAudioSeconds": round(first_audio - started, 3) if first_audio else None,
        "totalSeconds": round(elapsed, 3),
        "audioSeconds": round(len(pcm) / 48_000, 3),
        "chunks": len(chunk_times),
        "maximumChunkIntervalSeconds": round(max(intervals), 3) if intervals else None,
        "terminal": events[-1].type,
    }


def cancellation(adapter: ValidatedStreamingTts) -> dict:
    cancelled = Event()
    request = StreamingTtsRequest(
        uuid4(),
        "Dies ist ein absichtlich längerer Satz, dessen Erzeugung sofort abgebrochen werden soll, sobald das erste Audiostück eingetroffen ist.",
        "de", "velora-f", 99, True,
    )
    result = {}

    def consume() -> None:
        for event in adapter.stream(request, cancelled):
            if event.type == "audio" and "signal" not in result:
                result["signal"] = time.perf_counter()
                cancelled.set()
            if event.type in {"complete", "cancelled"}:
                result["terminal"] = event.type
                result["stopped"] = time.perf_counter()

    thread = threading.Thread(target=consume)
    thread.start()
    thread.join(timeout=60)
    if thread.is_alive():
        raise RuntimeError("Cancellation acceptance timed out")
    return {
        "terminal": result.get("terminal"),
        "signalToStopMilliseconds": round(
            (result["stopped"] - result["signal"]) * 1_000, 1
        ),
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=httpx.Timeout(300, connect=10)) as client:
        provider = QwenStreamingTtsAdapter.discover(BASE_URL, client)
        adapter = ValidatedStreamingTts(provider)
        results = [
            synthesize(adapter, index, locale, text)
            for index, (locale, text) in enumerate(PHRASES)
        ]
        report = {
            "capabilities": asdict(provider.capabilities),
            "phrases": results,
            "cancellation": cancellation(adapter),
        }
    path = OUTPUT / "acceptance.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Isolated realtime benchmark for NeMo-Speech.cpp's Nemotron ASR model."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
import urllib.request
import wave
from itertools import pairwise
from pathlib import Path

import psutil
import websockets

REFERENCES = [
    "Hey Velora, wie spät ist es?",
    "Schalte das Licht im Gamingraum ein.",
    "Stelle die Helligkeit im Wohnzimmer auf fünfunddreißig Prozent.",
    "Mach bitte beide Lampen aus.",
    "Welche Geräte sind momentan nicht erreichbar?",
    "Erinnere mich morgen früh daran, die Pflanzen zu gießen.",
    "Nein, nicht das Wohnzimmer, ich meinte den Gamingraum.",
    "Stopp, das möchte ich doch nicht ausführen.",
    "Die Temperatur im Arbeitszimmer soll heute Abend etwas niedriger sein.",
    "Wenn ich nach Hause komme, schalte zuerst das Licht ein und erzähle mir danach, was heute wichtig war.",
    "Natürlich, wir können später weitermachen, aber zuerst möchte ich wissen, ob im Haus noch irgendwo Licht brennt.",
    "Ich bin mir nicht sicher, ob ich die linke Lampe oder die Lampe neben dem Fenster gemeint habe.",
    "Hey Velora, what time is it?",
    "Turn on the lights in the living room.",
    "Set the bedroom brightness to forty-five percent.",
    "No, I meant the gaming room, not the living room.",
    "Stop, I don't want to execute that command.",
    "Which devices are currently unavailable?",
    "When I get home, turn on the hallway light and tell me what happened today.",
    "I'm not sure whether I meant the desk lamp or the lamp next to the window.",
]


def normalize(value: str) -> list[str]:
    return re.findall(r"[a-zäöüß]+", value.lower().replace("’", "'"))


def edit_distance(left: list[str], right: list[str]) -> int:
    row = list(range(len(right) + 1))
    for i, lhs in enumerate(left, 1):
        nxt = [i]
        for j, rhs in enumerate(right, 1):
            nxt.append(min(nxt[-1] + 1, row[j] + 1, row[j - 1] + (lhs != rhs)))
        row = nxt
    return row[-1]


def process_usage(process: psutil.Process) -> tuple[float, int]:
    processes = [process]
    try:
        processes.extend(process.children(recursive=True))
    except psutil.Error:
        pass
    cpu = 0.0
    rss = 0
    for item in processes:
        try:
            cpu += item.cpu_percent(None)
            rss += item.memory_info().rss
        except psutil.Error:
            pass
    return cpu, rss


async def transcribe(uri: str, clip: Path, chunk_ms: int, index: int) -> dict:
    with wave.open(str(clip), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 16000)
        pcm = wav.readframes(wav.getnframes())
        duration = wav.getnframes() / wav.getframerate()

    language = "de-DE" if index <= 12 else "en-US"
    events: list[dict] = []
    loop = asyncio.get_running_loop()
    started = loop.time()
    audio_end = 0.0
    completed: dict | None = None
    async with websockets.connect(uri, max_size=4 * 1024 * 1024) as socket:
        created = json.loads(await socket.recv())
        assert created["type"] == "session.created", created
        await socket.send(json.dumps({
            "type": "session.update",
            "session": {
                "sample_rate": 16000,
                "language": language,
                "automatic_punctuation": True,
                "word_timestamps": True,
                "endpointing_ms": 800,
            },
        }))
        updated = json.loads(await socket.recv())
        assert updated["type"] == "session.updated", updated

        async def receive() -> None:
            nonlocal completed
            while True:
                message = json.loads(await socket.recv())
                message["received_s"] = loop.time() - started
                events.append(message)
                if message["type"].endswith(".completed"):
                    completed = message
                    return
                if message["type"] == "error":
                    raise RuntimeError(message)

        receiver = asyncio.create_task(receive())
        chunk_bytes = int(16000 * 2 * chunk_ms / 1000)
        for offset in range(0, len(pcm), chunk_bytes):
            target = started + offset / (16000 * 2)
            await asyncio.sleep(max(0.0, target - loop.time()))
            await socket.send(pcm[offset : offset + chunk_bytes])
        audio_end = loop.time() - started
        await socket.send(json.dumps({"type": "input_audio_buffer.commit"}))
        try:
            await asyncio.wait_for(receiver, timeout=15)
        except TimeoutError:
            receiver.cancel()
            raise RuntimeError(f"no final event for {clip.name}")

    deltas = [event for event in events if event["type"].endswith(".delta")]
    useful = [
        event for event in deltas
        if len(normalize(str(event.get("delta", event.get("text", ""))))) >= 1
    ]
    final_text = str((completed or {}).get("transcript", (completed or {}).get("text", "")))
    reference = REFERENCES[index - 1] if index <= 20 else ""
    ref_words = normalize(reference)
    final_words = normalize(final_text)
    update_times = [event["received_s"] for event in useful]
    return {
        "clip": clip.name,
        "index": index,
        "language": language,
        "duration_s": round(duration, 3),
        "reference": reference,
        "final": final_text,
        "word_errors": edit_distance(ref_words, final_words) if ref_words else None,
        "reference_words": len(ref_words) if ref_words else None,
        "first_usable_partial_s": round(update_times[0], 4) if update_times else None,
        "partial_update_intervals_s": [round(b - a, 4) for a, b in pairwise(update_times)],
        "partial_count": len(deltas),
        "audio_send_end_s": round(audio_end, 4),
        "eos_to_final_s": round((completed or {}).get("received_s", audio_end) - audio_end, 4),
        "events": events,
    }


async def run(args: argparse.Namespace) -> None:
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".server.log")
    command = [
        args.binary, "serve", "--no-ui", "--host", "127.0.0.1", "--port", str(args.port),
        "--asr-model", args.model, "--device", "cpu",
        "--asr.streaming.chunk_size", str(args.chunk_ms / 1000),
    ]
    log = log_path.open("w", encoding="utf-8")
    server = await asyncio.create_subprocess_exec(
        *command, stdout=log, stderr=asyncio.subprocess.STDOUT
    )
    process = psutil.Process(server.pid)
    samples: list[dict] = []
    results: list[dict] = []
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            def is_ready() -> bool:
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{args.port}/ready", timeout=1
                    ) as response:
                        return bool(json.load(response).get("ready"))
                except (OSError, ValueError):
                    return False

            if await asyncio.to_thread(is_ready):
                break
            await asyncio.sleep(0.25)
        else:
            raise RuntimeError("server readiness timeout")

        process_usage(process)
        clips = sorted(Path(args.clips).glob("clip-*.wav"))
        for index, clip in enumerate(clips, 1):
            task = asyncio.create_task(transcribe(
                f"ws://127.0.0.1:{args.port}/v1/realtime", clip, args.chunk_ms, index
            ))
            while not task.done():
                await asyncio.sleep(0.1)
                cpu, rss = process_usage(process)
                samples.append({"at": time.time(), "cpu_percent": cpu, "rss_bytes": rss})
            result = await task
            results.append(result)
            print(f"{clip.name}: {result['final']!r} eos={result['eos_to_final_s']}s", flush=True)

        speech = results[:20]
        errors = sum(item["word_errors"] for item in speech)
        words = sum(item["reference_words"] for item in speech)
        partials = [item["first_usable_partial_s"] for item in speech if item["first_usable_partial_s"] is not None]
        intervals = [value for item in speech for value in item["partial_update_intervals_s"]]
        report = {
            "runtime": "NeMo-Speech.cpp 1.0.0 CPU Q8",
            "source_commit": "5be7bfb104802131e61fe679b3f1401b27270216",
            "model": args.model,
            "chunk_ms": args.chunk_ms,
            "summary": {
                "wer": errors / words,
                "word_errors": errors,
                "reference_words": words,
                "mean_first_usable_partial_s": sum(partials) / len(partials) if partials else None,
                "mean_partial_update_interval_s": sum(intervals) / len(intervals) if intervals else None,
                "mean_eos_to_final_s": sum(item["eos_to_final_s"] for item in speech) / len(speech),
                "max_eos_to_final_s": max(item["eos_to_final_s"] for item in speech),
                "max_cpu_percent": max(item["cpu_percent"] for item in samples),
                "max_rss_bytes": max(item["rss_bytes"] for item in samples),
                "non_speech_hallucinations": sum(bool(normalize(item["final"])) for item in results[20:]),
            },
            "results": results,
            "resource_samples": samples,
        }
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report["summary"], indent=2), flush=True)
    finally:
        server.terminate()
        try:
            await asyncio.wait_for(server.wait(), timeout=10)
        except TimeoutError:
            server.kill()
            await server.wait()
        log.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--clips", required=True)
    parser.add_argument("--chunk-ms", type=int, choices=(160, 320, 560), required=True)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--output", required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Silent Pi acceptance for downlink -> jitter buffer -> PipeWire."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
import uuid
from dataclasses import asdict
from pathlib import Path
from threading import Event, Thread

from kyrion_voice_satellite.pcm_downlink import PcmDownlinkClient
from kyrion_voice_satellite.pcm_jitter_buffer import PcmJitterBuffer
from kyrion_voice_satellite.pcm_pipewire import PipeWirePcmSink


def open_session(config: dict) -> tuple[dict, int]:
    token = Path(config["credential_file"]).read_text(encoding="utf-8").strip()
    request = urllib.request.Request(
        f"{config['core_url'].rstrip('/')}/v1/voice-satellite/sessions",
        data=b"",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Kyrion-Satellite-Id": config["satellite_id"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        session = json.load(response)
    received_at = time.time_ns() // 1_000_000
    return session, int(session["serverTimeEpochMillis"]) - received_at


def run(
    config: dict,
    duration_ms: int,
    cancel_after: float | None,
    *,
    signal: str = "silence",
) -> dict:
    session, clock_offset = open_session(config)
    buffer = PcmJitterBuffer()
    sink = PipeWirePcmSink(config.get("playback_target"))
    network_cancel = Event()
    downlink = {}

    def produce() -> None:
        downlink["result"] = PcmDownlinkClient(
            config["core_url"],
            config["satellite_id"],
            Path(config["credential_file"]),
        ).receive(
            session["sessionId"],
            str(uuid.uuid4()),
            duration_ms,
            buffer.push,
            clock_offset_millis=clock_offset,
            cancelled=network_cancel,
            signal=signal,
        )
        if downlink["result"].status == "cancelled":
            buffer.cancel()
        else:
            buffer.complete()

    producer = Thread(target=produce)
    producer.start()
    if cancel_after is not None:
        Thread(target=lambda: (time.sleep(cancel_after), network_cancel.set())).start()
    started = time.monotonic()
    buffer_result = buffer.play(sink.write)
    playback_result = sink.cancel() if buffer_result.cancelled else sink.complete()
    producer.join(timeout=2)
    if producer.is_alive():
        raise RuntimeError("PipeWire acceptance producer did not stop")
    return {
        "elapsed_seconds": time.monotonic() - started,
        "downlink": asdict(downlink["result"]),
        "buffer": asdict(buffer_result),
        "pipewire": asdict(playback_result),
    }


def run_buffered_tone(config: dict) -> dict:
    session, clock_offset = open_session(config)
    frames = []
    downlink = PcmDownlinkClient(
        config["core_url"],
        config["satellite_id"],
        Path(config["credential_file"]),
    ).receive(
        session["sessionId"],
        str(uuid.uuid4()),
        1_600,
        frames.append,
        clock_offset_millis=clock_offset,
        signal="tone",
    )
    sink = PipeWirePcmSink(config.get("playback_target"))
    started = time.monotonic()
    for frame in frames:
        sink.write(frame)
    playback = sink.complete()
    return {
        "playback_elapsed_seconds": time.monotonic() - started,
        "downlink": asdict(downlink),
        "pipewire": asdict(playback),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--audible-tone", action="store_true")
    parser.add_argument("--audible-tone-buffered", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.audible_tone_buffered:
        print(json.dumps({"buffered_tone": run_buffered_tone(config)}, indent=2))
        return
    print(
        json.dumps(
            {
                "complete": run(
                    config,
                    1_600 if args.audible_tone else 3_200,
                    None,
                    signal="tone" if args.audible_tone else "silence",
                ),
                "cancelled": None if args.audible_tone else run(config, 3_200, 0.8),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

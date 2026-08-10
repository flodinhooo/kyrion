#!/usr/bin/env python3
"""Silent physical acceptance for the bounded Satellite PCM jitter buffer."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
import uuid
from dataclasses import asdict
from pathlib import Path
from threading import Event, Thread

from kyrion_voice_satellite.pcm_downlink import PcmDownlinkClient, PcmDownlinkError
from kyrion_voice_satellite.pcm_jitter_buffer import (
    PcmJitterBuffer,
    PcmJitterBufferError,
)


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


def stream_once(client, session_id, clock_offset, duration_ms):
    buffer = PcmJitterBuffer()
    downlink = {}
    failure = []

    def produce():
        try:
            downlink["result"] = client.receive(
                session_id,
                str(uuid.uuid4()),
                duration_ms,
                buffer.push,
                clock_offset_millis=clock_offset,
            )
            buffer.complete()
        except (PcmDownlinkError, PcmJitterBufferError) as error:
            failure.append(error)
            buffer.cancel()

    producer = Thread(target=produce)
    started = time.monotonic()
    producer.start()
    metrics = buffer.play(lambda _frame: None)
    producer.join(timeout=5)
    if producer.is_alive():
        raise RuntimeError("PCM producer did not stop")
    if failure:
        raise failure[0]
    return {
        "elapsed_seconds": time.monotonic() - started,
        "downlink": asdict(downlink["result"]),
        "buffer": asdict(metrics),
    }


def cancellation(client, session_id, clock_offset):
    buffer = PcmJitterBuffer()
    network_cancel = Event()
    downlink = {}

    def produce():
        downlink["result"] = client.receive(
            session_id,
            str(uuid.uuid4()),
            3_200,
            buffer.push,
            clock_offset_millis=clock_offset,
            cancelled=network_cancel,
        )
        if downlink["result"].status == "cancelled":
            buffer.cancel()
        else:
            buffer.complete()

    def cancel():
        time.sleep(0.8)
        network_cancel.set()

    producer = Thread(target=produce)
    canceller = Thread(target=cancel)
    producer.start()
    canceller.start()
    started = time.monotonic()
    metrics = buffer.play(lambda _frame: None)
    stopped_after = time.monotonic() - started
    producer.join(timeout=2)
    canceller.join(timeout=2)
    if producer.is_alive():
        raise RuntimeError("Cancelled PCM producer did not stop")
    return {
        "stopped_after_seconds": stopped_after,
        "downlink": asdict(downlink["result"]),
        "buffer": asdict(metrics),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--duration-ms", type=int, default=20_000)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    session, clock_offset = open_session(config)
    client = PcmDownlinkClient(
        config["core_url"], config["satellite_id"], Path(config["credential_file"])
    )
    print(
        json.dumps(
            {
                "session_id": session["sessionId"],
                "clock_offset_millis": clock_offset,
                "stream": stream_once(
                    client, session["sessionId"], clock_offset, args.duration_ms
                ),
                "cancellation": cancellation(
                    client, session["sessionId"], clock_offset
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Physical Pi acceptance runner for the isolated Phase 3.3 PCM downlink."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
import urllib.request
import uuid
from dataclasses import asdict
from pathlib import Path
from threading import Event

from kyrion_voice_satellite.pcm_downlink import PcmDownlinkClient, PcmDownlinkError


def request_json(url: str, satellite_id: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        data=b"",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Kyrion-Satellite-Id": satellite_id,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--duration-ms", type=int, default=20_000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    credential_file = Path(config["credential_file"])
    token = credential_file.read_text(encoding="utf-8").strip()
    core_url = config["core_url"].rstrip("/")
    satellite_id = config["satellite_id"]
    session = request_json(
        f"{core_url}/v1/voice-satellite/sessions", satellite_id, token
    )
    received_at = time.time_ns() // 1_000_000
    clock_offset = int(session["serverTimeEpochMillis"]) - received_at
    client = PcmDownlinkClient(core_url, satellite_id, credential_file)

    runs = []
    for _ in range(args.repeats):
        started = time.monotonic()
        result = client.receive(
            session["sessionId"],
            str(uuid.uuid4()),
            args.duration_ms,
            lambda _frame: None,
            clock_offset_millis=clock_offset,
        )
        runs.append({**asdict(result), "elapsed_seconds": time.monotonic() - started})

    cancelled = Event()
    cancelled_frames = 0

    def cancel_after_first(_frame: bytes) -> None:
        nonlocal cancelled_frames
        cancelled_frames += 1
        cancelled.set()

    cancelled_started = time.monotonic()
    cancelled_result = client.receive(
        session["sessionId"],
        str(uuid.uuid4()),
        1_600,
        cancel_after_first,
        clock_offset_millis=clock_offset,
        cancelled=cancelled,
    )
    cancelled_elapsed = time.monotonic() - cancelled_started
    reconnect = client.receive(
        session["sessionId"],
        str(uuid.uuid4()),
        320,
        lambda _frame: None,
        clock_offset_millis=clock_offset,
    )

    authentication_rejected = False
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as wrong:
        wrong.write("wrong-token")
        wrong.flush()
        try:
            PcmDownlinkClient(core_url, satellite_id, Path(wrong.name)).receive(
                session["sessionId"], str(uuid.uuid4()), 80, lambda _frame: None
            )
        except PcmDownlinkError:
            authentication_rejected = True

    print(
        json.dumps(
            {
                "session_id": session["sessionId"],
                "clock_offset_millis": clock_offset,
                "runs": runs,
                "cancelled": {
                    **asdict(cancelled_result),
                    "sink_frames": cancelled_frames,
                    "elapsed_seconds": cancelled_elapsed,
                },
                "reconnect": asdict(reconnect),
                "authentication_rejected": authentication_rejected,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

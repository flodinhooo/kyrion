"""Explicit operator probe; no device execution, credential output or audio retention."""

from __future__ import annotations

import argparse
import array
import io
import json
import math
import time
import uuid
import wave
from pathlib import Path

from kyrion_voice_satellite import core_client
from kyrion_voice_satellite.audio import AlsaCapture
from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.detector import OpenWakeWordDetector
from kyrion_voice_satellite.playback import PipeWirePlayback
from kyrion_voice_satellite.utterance import capture_utterance
from kyrion_voice_satellite.vad import WebRtcVoiceActivityDetector
from kyrion_voice_satellite.wav import pcm_to_wav


class SafeClient(core_client.CoreVoiceClient):
    def _request(self, method, path, *args, **kwargs):
        if path.endswith(("/execute", "/playback-completed")):
            raise core_client.CoreVoiceError("OPERATOR_PROBE_ACTION_FORBIDDEN")
        return super()._request(method, path, *args, **kwargs)


def fixture_audio(path: Path) -> bytes:
    data = path.read_bytes()
    if len(data) > 2_000_000:
        raise ValueError("FIXTURE_TOO_LARGE")
    with wave.open(io.BytesIO(data)) as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (
            1,
            2,
            16000,
        ):
            raise ValueError("FIXTURE_FORMAT_INVALID")
    return data


def probe(args) -> dict:
    config = SatelliteConfig.load(Path.home() / ".config/kyrion/voice-satellite.json")
    result = {
        "microphoneOpened": False,
        "wakeDetected": False,
        "playbackCompleted": False,
        "audibilityVerified": False,
        "firstAudibleAudioMs": None,
        "firstModelOutputMs": None,
        "deviceExecutionPermitted": False,
        "inputSource": "synthetic_wav" if args.fixture else "microphone",
    }
    vad = WebRtcVoiceActivityDetector()
    if args.capture_seconds:
        detector = OpenWakeWordDetector(config.model_path)
        frames = AlsaCapture(config.capture_device).frames()
        samples = array.array("h")
        speech_frames = 0
        maximum_score = 0.0
        try:
            for _ in range(int(args.capture_seconds / 0.08)):
                frame = next(frames)
                result["microphoneOpened"] = True
                samples.frombytes(frame)
                speech_frames += int(vad.is_speech(frame))
                maximum_score = max(maximum_score, detector.score(frame))
        finally:
            frames.close()
        result.update(
            sampleRate=16000,
            channels=1,
            sampleWidth=2,
            capturedSamples=len(samples),
            rms=round(
                math.sqrt(
                    sum(value * value for value in samples) / max(1, len(samples))
                ),
                2,
            ),
            speechFrames=speech_frames,
            maximumWakeScore=round(maximum_score, 5),
            wakeDetected=maximum_score >= config.threshold,
        )
    if not args.dialogue:
        return result
    client = SafeClient(config.core_url, config.satellite_id, config.credential_file)
    session = client.open_session()
    result["authenticatedSessionOpened"] = True
    result["conversationId"] = session.conversation_id
    try:
        if args.fixture:
            wav = fixture_audio(args.fixture)
        else:
            greeting = client.greeting(session.id, config.locale)
            if args.play:
                PipeWirePlayback(config.playback_target).play(greeting)
            print("READY_FOR_GERMAN_SPEECH", flush=True)
            frames = AlsaCapture(config.capture_device).frames()
            try:
                utterance = capture_utterance(
                    frames,
                    vad,
                    start_timeout_seconds=10,
                    end_silence_seconds=config.speech_end_silence_seconds,
                    max_seconds=20,
                )
            finally:
                frames.close()
            if utterance is None:
                raise ValueError("NO_SPEECH_CAPTURED")
            result["microphoneOpened"] = True
            wav = pcm_to_wav(utterance.pcm)
        started = time.monotonic()
        original_open = core_client.open_core_url

        class ObservedResponse:
            def __init__(self, response):
                self.response = response

            def __enter__(self):
                self.response.__enter__()
                return self

            def __exit__(self, *values):
                return self.response.__exit__(*values)

            def __iter__(self):
                for line in self.response:
                    if line.strip() and json.loads(line).get("type") == "transcript":
                        result.setdefault(
                            "captureEndToTranscriptMs",
                            round((time.monotonic() - started) * 1000),
                        )
                    yield line

            def read(self, *values):
                return self.response.read(*values)

        def observed_open(request, **values):
            response = original_open(request, **values)
            return (
                ObservedResponse(response)
                if request.full_url.endswith("/turns")
                else response
            )

        def play(audio):
            result.setdefault(
                "captureEndToFirstAudioReceivedMs",
                round((time.monotonic() - started) * 1000),
            )
            if args.play:
                result.setdefault(
                    "captureEndToPlaybackProcessMs",
                    round((time.monotonic() - started) * 1000),
                )
                PipeWirePlayback(config.playback_target).play(audio)
                result["playbackCompleted"] = True

        turn_id = str(uuid.uuid4())
        result["turnId"] = turn_id
        core_client.open_core_url = observed_open
        try:
            turn = client.turn(session.id, wav, config.locale, play, turn_id)
        except (OSError, RuntimeError, ValueError) as error:
            result.update(
                failed=True,
                code=type(error).__name__,
                totalTurnMs=round((time.monotonic() - started) * 1000),
            )
            return result
        finally:
            core_client.open_core_url = original_open
        result.update(
            transcriptChars=len(turn.transcript),
            responseChars=len(turn.response_text),
            turnCompleted=True,
            totalTurnMs=round((time.monotonic() - started) * 1000),
        )
    finally:
        client.close_session(session.id, "explicit")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--capture-seconds", type=float, default=0, choices=[0, 3, 5, 15]
    )
    parser.add_argument("--dialogue", action="store_true")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--play", action="store_true")
    arguments = parser.parse_args()
    try:
        summary = probe(arguments)
        print(json.dumps(summary))
        if summary.get("failed"):
            raise SystemExit(1)
    except (OSError, RuntimeError, ValueError, wave.Error) as error:
        print(
            json.dumps(
                {
                    "failed": True,
                    "code": type(error).__name__,
                    "audibilityVerified": False,
                }
            )
        )
        raise SystemExit(1) from None

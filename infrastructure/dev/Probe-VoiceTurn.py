"""Synthetic stop-turn acceptance. No microphone, speaker or device execution."""
from __future__ import annotations

import io
import socket
import uuid
import wave
from pathlib import Path
from urllib.parse import urlsplit

from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.core_client import CoreVoiceClient, CoreVoiceError


class ReadOnlyActionClient(CoreVoiceClient):
    def _request(self, method, path, body, content_type, extra_headers=None):
        if path.endswith('/execute') or path.endswith('/playback-completed'):
            raise CoreVoiceError('OPERATOR_PROBE_ACTION_FORBIDDEN')
        return super()._request(method, path, body, content_type, extra_headers)


def probe(audio: bytes) -> dict[str, object]:
    config = SatelliteConfig.load(Path.home() / '.config/kyrion/voice-satellite.json')
    result: dict[str, object] = {'authenticatedSessionOpened': False,
                                 'stopTranscribed': False, 'responseAudioValid': False, 'turnCompleted': False,
                                 'sessionClosed': False, 'playbackPerformed': False, 'microphoneOpened': False,
                                 'ipv4DiagnosticOverride': True, 'deviceExecutionPermitted': False}
    original = socket.getaddrinfo
    host = urlsplit(config.core_url).hostname

    def ipv4_core(address, port, family=0, type=0, proto=0, flags=0):
        return original(address, port, socket.AF_INET if address == host else family,
                        type, proto, flags)

    socket.getaddrinfo = ipv4_core
    client = ReadOnlyActionClient(config.core_url, config.satellite_id, config.credential_file)
    session = None
    chunks = []

    def validate_chunk(chunk):
        with wave.open(io.BytesIO(chunk)) as wav:
            if wav.getnframes() < 1 or wav.getnchannels() not in (1, 2):
                raise ValueError('INVALID_AUDIO')
            chunks.append(wav.getframerate())

    try:
        session = client.open_session()
        result['authenticatedSessionOpened'] = True
        turn = client.turn(session.id, audio, config.locale, validate_chunk, str(uuid.uuid4()))
        words = turn.transcript.lower().strip().strip('.!?,')
        result['stopTranscribed'] = words in ('stop', 'stopp')
        result['responseAudioValid'] = bool(chunks)
        result['sampleRates'] = sorted(set(chunks))
        result['turnCompleted'] = bool(turn.response_text) and not turn.continue_session
    except (OSError, RuntimeError, ValueError, wave.Error) as error:
        result['code'] = type(error).__name__
    finally:
        try:
            if session:
                client.close_session(session.id, 'explicit')
                result['sessionClosed'] = True
        except (OSError, RuntimeError) as error:
            result['closeCode'] = type(error).__name__
        finally:
            socket.getaddrinfo = original
    return result

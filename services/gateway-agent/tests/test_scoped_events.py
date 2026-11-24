"""Actual Linux/Windows pipes, synthetic MQTT bytes; no broker or household devices."""

import os
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from kyrion_gateway_agent.cli import _scoped_event_lines

pytestmark = pytest.mark.skipif(
    not (sys.platform.startswith("linux") or os.name == "nt"), reason="Supported native pipe APIs"
)


def test_revoked_gate_stops_before_reading_event_bytes():
    reader, writer = os.pipe()
    os.close(writer)
    with os.fdopen(reader, "rb", buffering=0) as stream, patch("os.read") as read:
        assert (
            list(
                _scoped_event_lines(
                    SimpleNamespace(stdout=stream), lambda: False, threading.Event()
                )
            )
            == []
        )
    read.assert_not_called()


def read_synthetic(data):
    reader, writer = os.pipe()

    def send():
        try:
            with os.fdopen(writer, "wb") as stream:
                stream.write(data)
        except BrokenPipeError:
            pass

    producer = threading.Thread(target=send, daemon=True)
    producer.start()
    with os.fdopen(reader, "rb", buffering=0) as stream:
        lines = list(
            _scoped_event_lines(SimpleNamespace(stdout=stream), lambda: True, threading.Event())
        )
    producer.join(timeout=2)
    assert not producer.is_alive()
    return lines


def test_invalid_utf8_and_oversized_event_lines_cannot_reach_parser():
    assert read_synthetic(b"first\n\xff\n" + b"x" * 20000 + b"\nlast\n") == ["first", "last"]


def test_unterminated_oversized_stream_is_bounded_and_closed():
    assert read_synthetic(b"x" * 100000) == []


def test_idle_pipe_stops_after_permission_revocation_without_waiting_for_writer():
    reader, writer = os.pipe()
    deadline = time.monotonic() + 0.1
    try:
        with os.fdopen(reader, "rb", buffering=0) as stream:
            result = list(
                _scoped_event_lines(
                    SimpleNamespace(stdout=stream),
                    lambda: time.monotonic() < deadline,
                    threading.Event(),
                )
            )
        assert result == []
        assert time.monotonic() - deadline < 1
    finally:
        os.close(writer)


def test_buffered_second_event_is_not_yielded_after_permission_revocation():
    reader, writer = os.pipe()
    os.write(writer, b"first\nsecond\n")
    os.close(writer)
    allowed = True
    with os.fdopen(reader, "rb", buffering=0) as stream:
        lines = _scoped_event_lines(
            SimpleNamespace(stdout=stream), lambda: allowed, threading.Event()
        )
        assert next(lines) == "first"
        allowed = False
        assert list(lines) == []

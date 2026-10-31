import logging
from uuid import uuid4

import pytest

from kyrion_ai.voice_trace import correlation, mark, measured_call, scope


def test_correlation_is_uuid_only_and_scopes_do_not_leak(caplog):
    caplog.set_level(logging.INFO)
    identifier = str(uuid4())
    with scope(identifier):
        mark("stt.start")
        with scope("private text\nAuthorization: Bearer secret"):
            mark("not.recorded")
        assert correlation.get() == identifier
        mark("stt.end", bytes=44)
    assert correlation.get() is None
    assert len(caplog.records) == 2
    assert all(identifier in item.message and "mono_ns=" in item.message for item in caplog.records)
    assert "secret" not in caplog.text
    assert "private" not in caplog.text


def test_failed_worker_keeps_end_boundary_and_cleans_context(caplog):
    caplog.set_level(logging.INFO)

    def fail():
        raise ValueError("synthetic")

    with pytest.raises(ValueError, match="synthetic"):
        measured_call(str(uuid4()), "tts", fail)
    assert [item.message.split("stage=")[1].split()[0] for item in caplog.records] == [
        "tts.worker_start",
        "tts.worker_end",
    ]
    assert correlation.get() is None

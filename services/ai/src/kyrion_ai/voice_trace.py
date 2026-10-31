"""Content-free, process-local monotonic voice timing, opt-in through a UUID header."""

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

correlation: ContextVar[str | None] = ContextVar("voice_correlation", default=None)
logger = logging.getLogger("uvicorn.error.kyrion-ai.voice")


def mark(stage: str, **metrics: int) -> None:
    if identifier := correlation.get():
        logger.info(
            "VOICE_TIMING id=%s stage=%s mono_ns=%s metrics=%s",
            identifier,
            stage,
            time.monotonic_ns(),
            metrics,
        )


@contextmanager
def scope(value: str | None):
    try:
        identifier = str(UUID(value)) if value else None
    except ValueError:
        identifier = None
    token = correlation.set(identifier)
    try:
        yield
    finally:
        correlation.reset(token)


def measured_call(identifier, stage, function, *args):
    with scope(identifier):
        mark(stage + ".worker_start")
        try:
            return function(*args)
        finally:
            mark(stage + ".worker_end")

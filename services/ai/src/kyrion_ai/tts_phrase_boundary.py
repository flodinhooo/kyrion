from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from threading import Event

MIN_PHRASE_CHARACTERS = 12
MAX_PHRASE_CHARACTERS = 180
SOFT_BOUNDARIES = ".!?;:"
NON_TERMINAL_ABBREVIATIONS = {
    "bzw.",
    "ca.",
    "dr.",
    "e.g.",
    "etc.",
    "i.e.",
    "mr.",
    "mrs.",
    "prof.",
    "u.a.",
    "z.b.",
}


@dataclass(frozen=True, slots=True)
class TtsPhrase:
    text: str
    index: int
    final: bool


def segment_tts_phrases(tokens: Iterable[str], cancelled: Event) -> Iterator[TtsPhrase]:
    """Turn an LLM text stream into bounded provider-neutral TTS phrases."""

    buffer = ""
    index = 0
    for token in tokens:
        if cancelled.is_set():
            return
        buffer += token
        while boundary := _next_boundary(buffer):
            phrase, buffer = buffer[:boundary].strip(), buffer[boundary:].lstrip()
            if phrase:
                yield TtsPhrase(phrase, index, False)
                index += 1

    if not cancelled.is_set() and (phrase := buffer.strip()):
        yield TtsPhrase(phrase, index, True)


def _next_boundary(value: str) -> int | None:
    for position, character in enumerate(value):
        end = position + 1
        if character in SOFT_BOUNDARIES and end >= MIN_PHRASE_CHARACTERS:
            candidate = value[:end].lower().split()[-1]
            if candidate not in NON_TERMINAL_ABBREVIATIONS:
                return end
    if len(value) <= MAX_PHRASE_CHARACTERS:
        return None
    split = value.rfind(" ", 0, MAX_PHRASE_CHARACTERS + 1)
    return split if split >= MIN_PHRASE_CHARACTERS else MAX_PHRASE_CHARACTERS

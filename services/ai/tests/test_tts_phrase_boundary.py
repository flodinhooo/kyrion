from threading import Event

from kyrion_ai.tts_phrase_boundary import MAX_PHRASE_CHARACTERS, segment_tts_phrases


def test_emits_complete_sentences_before_stream_completion() -> None:
    phrases = list(segment_tts_phrases(["Guten Morgen. Wie ", "kann ich helfen?"], Event()))

    assert [(phrase.text, phrase.index, phrase.final) for phrase in phrases] == [
        ("Guten Morgen.", 0, False),
        ("Wie kann ich helfen?", 1, False),
    ]


def test_preserves_domain_names_and_flushes_unpunctuated_tail() -> None:
    phrases = list(
        segment_tts_phrases(
            ["Ich schalte die desk lamp im ", "Gamingraum für Velora ein"], Event()
        )
    )

    assert [(phrase.text, phrase.final) for phrase in phrases] == [
        ("Ich schalte die desk lamp im Gamingraum für Velora ein", True)
    ]


def test_does_not_split_known_abbreviation() -> None:
    phrases = list(segment_tts_phrases(["Das gilt z.B. heute. Danach geht es weiter."], Event()))

    assert [phrase.text for phrase in phrases] == [
        "Das gilt z.B. heute.",
        "Danach geht es weiter.",
    ]


def test_hard_limit_splits_at_whitespace() -> None:
    text = "Wort " * 80
    phrases = list(segment_tts_phrases([text], Event()))

    assert len(phrases) > 1
    assert all(len(phrase.text) <= MAX_PHRASE_CHARACTERS for phrase in phrases)
    assert " ".join(phrase.text for phrase in phrases) == text.strip()


def test_cancellation_discards_buffered_and_later_text() -> None:
    cancelled = Event()

    def tokens():
        yield "Die erste Antwort ist fertig."
        cancelled.set()
        yield " Dieser Text darf nicht erscheinen."

    phrases = list(segment_tts_phrases(tokens(), cancelled))

    assert [phrase.text for phrase in phrases] == ["Die erste Antwort ist fertig."]

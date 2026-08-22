package dev.kyrion.core.voice

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.ValueSource

class VoiceSessionEndIntentTest {
    @ParameterizedTest
    @ValueSource(strings = ["Hey Velora", "Hey Willorra!", "Hey, Fedora?"])
    fun `recognises repeated wake word as session restart`(transcript: String) {
        assertThat(isVoiceSessionRestart(transcript)).isTrue()
    }

    @ParameterizedTest
    @ValueSource(
        strings = [
            "Bis später.",
            "Danke, bis später.",
            "Passt. Danke. Bis später.",
            "Okay, tschüss.",
            "Danke dir, das war's.",
            "Okay, danke dir, bis spaeter!",
            "Alright, goodbye.",
            "Thanks, talk to you later.",
        ],
    )
    fun `recognises natural terminal utterances`(transcript: String) {
        assertThat(isVoiceSessionEnd(transcript)).isTrue()
    }

    @ParameterizedTest
    @ValueSource(
        strings = [
            "Sag mir, was 'bis später' bedeutet.",
            "Wie sagt man tschüss auf Spanisch?",
            "Bitte erkläre den Ausdruck das war's.",
            "Wir sprechen später über Madrid.",
            "Danke für die Erklärung, aber ich habe noch eine Frage.",
            "Ist goodbye dasselbe wie auf Wiedersehen?",
        ],
    )
    fun `does not end on quoted or contextual mentions`(transcript: String) {
        assertThat(isVoiceSessionEnd(transcript)).isFalse()
    }

    @ParameterizedTest
    @ValueSource(strings = ["Danke Velora.", "Vielen Dank, Velora!"])
    fun `recognises only explicit Velora gratitude endings`(transcript: String) {
        assertThat(isVoiceSessionGratitude(transcript)).isTrue()
    }

    @ParameterizedTest
    @ValueSource(strings = ["Danke.", "Vielen Dank.", "Danke Velora, aber ich habe noch eine Frage."])
    fun `does not mistake other gratitude for the explicit Velora ending`(transcript: String) {
        assertThat(isVoiceSessionGratitude(transcript)).isFalse()
    }
}

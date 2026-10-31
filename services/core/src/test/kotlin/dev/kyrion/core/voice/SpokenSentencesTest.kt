package dev.kyrion.core.voice

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class SpokenSentencesTest {
    @Test fun `complete sentences remain ordered and text is not lost or repeated`() {
        val text = "Die Luft streut blaues Licht besonders stark. Deshalb erscheint der Himmel blau."
        assertThat(spokenSentences(text)).hasSize(2)
        assertThat(spokenSentences(text).joinToString(" ")).isEqualTo(text)
    }

    @Test fun `small fragments stay together and request count is bounded`() {
        assertThat(spokenSentences("Ja. Das ist eine ausreichend lange Antwort dazu.")).hasSize(1)
        val text = List(20) { "Dies ist ein ausreichend langer vollständiger Satz." }.joinToString(" ")
        assertThat(spokenSentences(text)).hasSize(8)
        assertThat(spokenSentences(text).joinToString(" ")).isEqualTo(text)
        assertThat(spokenSentences("Ein Text ohne Satzende")).containsExactly("Ein Text ohne Satzende")
    }
}

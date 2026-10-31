package dev.kyrion.core.voice

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class SpokenSentencesTest {
    @Test fun `unicode bullets are whole items rather than a single buffered paragraph`() {
        val bullet = 0x2022.toChar()
        val text = "Three useful points:\n$bullet This is the first complete useful suggestion.\n$bullet This is the second complete useful suggestion."
        assertThat(spokenSentences(text)).hasSize(2)
        assertThat(spokenSentences(text).first()).contains("points:", "first complete")
    }
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
    @Test fun `list introduction stays with useful first item and the last item is retained`() {
        val text = "Hier sind drei M\u00f6glichkeiten, Wasser zu sparen:\n\n* Schalten Sie den Wasserhahn beim Z\u00e4hneputzen ab.\n* Nutzen Sie die Waschmaschine nur voll beladen.\n* Sammeln Sie Regenwasser f\u00fcr den Garten."
        val parts = spokenSentences(text)
        assertThat(parts).hasSize(3)
        assertThat(parts.first()).contains("M\u00f6glichkeiten", "Z\u00e4hneputzen")
        assertThat(parts.last()).endsWith("Garten.")
        assertThat(parts.joinToString(" ").replace(Regex("\\s+"), " "))
            .isEqualTo(text.replace(Regex("\\s+"), " "))
    }

    @Test fun `numbered list keeps short entries together and never releases an introduction alone`() {
        val parts = spokenSentences("Drei Punkte:\n1. Kurz.\n2. Ein vollst\u00e4ndiger ausreichend langer zweiter Punkt.\n3. Ende.")
        assertThat(parts.first()).contains("Kurz.", "zweiter Punkt.")
        assertThat(parts.last()).endsWith("Ende.")
        assertThat(parts).doesNotContain("Drei Punkte:")
    }
}

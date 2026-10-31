package dev.kyrion.core.voice

import java.text.BreakIterator
import java.util.Locale

/** Complete ordered sentences; no parallel synthesis, replay or model-text truncation. */
internal fun spokenSentences(text: String): List<String> {
    val boundaries = BreakIterator.getSentenceInstance(Locale.ROOT)
    boundaries.setText(text)
    val parts = mutableListOf<String>()
    val bullets = Regex("(?m)^[\\t ]*(?:[-*\\u2022]|\\d+[.)])[\\t ]+\\S").findAll(text).map { it.range.first }.toList()
    // An introductory colon is not an answer. Attach it to the first complete
    // list item, then release whole following items, including a final fragment.
    val ends = if (bullets.size >= 2) bullets.drop(1) + text.length else buildList {
        boundaries.first()
        var boundary = boundaries.next()
        while (boundary != BreakIterator.DONE) {
            add(boundary)
            boundary = boundaries.next()
        }
    }
    var start = 0
    var pending = ""
    for (end in ends) {
        pending += text.substring(start, end)
        // Keep tiny fragments/abbreviations together and cap the number of requests.
        if (pending.trim().length >= 32 && parts.size < 7) {
            parts.add(pending.trim())
            pending = ""
        }
        start = end
    }
    if (pending.isNotBlank()) parts.add(pending.trim())
    return parts.ifEmpty { listOf(text) }
}

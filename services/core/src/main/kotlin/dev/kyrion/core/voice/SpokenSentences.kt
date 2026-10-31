package dev.kyrion.core.voice

import java.text.BreakIterator
import java.util.Locale

/** Complete ordered sentences; no parallel synthesis, replay or model-text truncation. */
internal fun spokenSentences(text: String): List<String> {
    val boundaries = BreakIterator.getSentenceInstance(Locale.ROOT)
    boundaries.setText(text)
    val parts = mutableListOf<String>()
    var start = boundaries.first()
    var end = boundaries.next()
    var pending = ""
    while (end != BreakIterator.DONE) {
        pending += text.substring(start, end)
        // Keep tiny fragments/abbreviations together and cap the number of requests.
        if (pending.trim().length >= 32 && parts.size < 7) {
            parts.add(pending.trim())
            pending = ""
        }
        start = end
        end = boundaries.next()
    }
    if (pending.isNotBlank()) parts.add(pending.trim())
    return parts.ifEmpty { listOf(text) }
}

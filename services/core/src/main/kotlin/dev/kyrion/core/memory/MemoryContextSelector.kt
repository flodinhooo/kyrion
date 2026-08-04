package dev.kyrion.core.memory

import org.springframework.stereotype.Service
import java.text.Normalizer
import java.util.Locale
import java.util.UUID

@Service
class MemoryContextSelector(private val repository: PersonalMemoryRepository) {
    fun select(ownerId: UUID, query: String, limit: Int = 3): List<PersonalMemory> {
        if (!repository.settings(ownerId).enabled) return emptyList()
        val queryTerms = terms(query)
        if (queryTerms.isEmpty()) return emptyList()
        return repository.confirmed(ownerId, CANDIDATE_LIMIT)
            .map { memory -> memory to queryTerms.intersect(terms(memory.content)).size }
            .filter { (memory, score) -> score >= if (memory.sensitivity == MemorySensitivity.sensitive) 2 else 1 }
            .sortedWith(compareByDescending<Pair<PersonalMemory, Int>> { it.second }.thenByDescending { it.first.updatedAt })
            .take(limit.coerceIn(0, MAX_SELECTED))
            .map { it.first }
    }

    fun conflict(ownerId: UUID, content: String, category: MemoryCategory): PersonalMemory? {
        val proposedTerms = terms(content)
        return repository.confirmed(ownerId, CANDIDATE_LIMIT)
            .asSequence()
            .filter { it.category == category }
            .map { it to proposedTerms.intersect(terms(it.content)).size }
            .filter { it.second >= 2 }
            .sortedWith(compareByDescending<Pair<PersonalMemory, Int>> { it.second }.thenByDescending { it.first.updatedAt })
            .firstOrNull()?.first
    }

    internal fun terms(value: String): Set<String> = Normalizer.normalize(value.lowercase(Locale.ROOT), Normalizer.Form.NFKD)
        .replace(Regex("\\p{M}+"), "")
        .split(Regex("[^\\p{L}\\p{N}]+"))
        .asSequence()
        .filter { it.length >= 3 && it !in STOP_WORDS }
        .toSet()

    companion object {
        private const val CANDIDATE_LIMIT = 100
        private const val MAX_SELECTED = 3
        private val STOP_WORDS = setOf(
            "aber", "auch", "das", "dem", "den", "der", "die", "ein", "eine", "für", "ist", "mit", "nicht", "oder", "und", "von", "was", "wie",
            "and", "are", "for", "from", "how", "not", "that", "the", "this", "what", "with", "you", "your",
        )
    }
}

package dev.kyrion.core.context

import dev.kyrion.core.ai.AiFailure
import dev.kyrion.core.knowledge.application.KnowledgeService
import dev.kyrion.core.knowledge.domain.KnowledgeSource
import org.springframework.stereotype.Service
import java.util.UUID

@Service
class KnowledgeContextAssembler(
    private val knowledge: KnowledgeService,
    private val answerSources: dev.kyrion.core.knowledge.persistence.KnowledgeAnswerSources
) {
    fun verify(actor: UUID, sources: List<KnowledgeSource>) {
        sources.forEach { source ->
            val document = knowledge.document(actor, source.documentId)
            if (document.status != "READY" || source.reference.split(':')
                    .getOrNull(2) != document.ingestionRevision.toString()
            )
                throw AiFailure("CONTEXT_NOT_ALLOWED", 403)
        }
    }

    fun record(actor: UUID, conversation: UUID, message: UUID, sources: List<KnowledgeSource>) =
        answerSources.save(actor, conversation, message, sources)
    fun assemble(actor: UUID, query: String, budget: Int): List<KnowledgeSource> {
        if (budget < 256) throw AiFailure("CONTEXT_LIMIT_EXCEEDED")
        val spaces = knowledge.spaces(actor).map { it.id }
        if (spaces.isEmpty()) return emptyList()
        var remaining = minOf(budget, 1024) * 3 // Conservative UTF-8 bytes, including source metadata.
        return knowledge.search(actor, spaces, query, 3).mapNotNull { source ->
            val overhead = source.filename.toByteArray().size + source.reference.length + 160
            val available = remaining - overhead
            if (available < 100) return@mapNotNull null
            var excerpt = source.excerpt
            while (excerpt.toByteArray().size > available) excerpt = excerpt.dropLast(1)
            remaining -= excerpt.toByteArray().size + overhead
            source.copy(excerpt = excerpt, endOffset = source.startOffset + excerpt.length)
        }
    }
}

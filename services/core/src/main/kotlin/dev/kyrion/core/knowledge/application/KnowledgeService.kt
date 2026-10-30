package dev.kyrion.core.knowledge.application

import dev.kyrion.core.activity.*
import dev.kyrion.core.knowledge.domain.*
import dev.kyrion.core.knowledge.ingestion.*
import dev.kyrion.core.knowledge.persistence.KnowledgeRepository
import dev.kyrion.core.knowledge.storage.LocalKnowledgeObjectStore
import dev.kyrion.core.security.RbacService
import org.springframework.stereotype.Service
import java.io.InputStream
import java.nio.file.Files
import java.security.MessageDigest
import java.util.UUID

@Service
class KnowledgeService(
    private val repository: KnowledgeRepository, private val store: LocalKnowledgeObjectStore,
    private val text: KnowledgeText, private val embeddings: EmbeddingProvider,
    private val rbac: RbacService, private val activity: ActivityService,
) {
    fun spaces(actor: UUID): List<KnowledgeSpace> {
        rbac.require(actor, "knowledge:read"); return repository.spaces(actor)
    }

    fun createSpace(actor: UUID): KnowledgeSpace {
        rbac.require(actor, "knowledge:create"); return repository.createSpace(actor)
    }

    fun documents(actor: UUID, space: UUID, limit: Int, offset: Int): List<KnowledgeDocument> {
        rbac.require(actor, "knowledge:read")
        if (limit !in 1..100 || offset !in 0..10000) throw KnowledgeFailure("INVALID_REQUEST")
        return repository.list(actor, space, limit, offset)
    }

    fun document(actor: UUID, id: UUID): KnowledgeDocument {
        rbac.require(actor, "knowledge:read"); return repository.find(actor, id)
    }

    fun content(actor: UUID, id: UUID): Pair<KnowledgeDocument, java.nio.file.Path> {
        val document = document(actor, id)
        val path = store.path(repository.key(actor, id))
        if (!Files.isRegularFile(path)) throw KnowledgeFailure("KNOWLEDGE_FILE_UNAVAILABLE", 503)
        audit(actor, id, "knowledge.downloaded")
        return document to path
    }

    fun upload(actor: UUID, space: UUID, filename: String, mediaType: String, input: InputStream): KnowledgeDocument {
        rbac.require(actor, "knowledge:create"); repository.requireSpace(actor, space)
        if (filename.isBlank() || filename.length > 200 || filename.any { it.code < 32 || it in "/\\" } || filename in setOf(
                ".",
                ".."
            ))
            throw KnowledgeFailure("KNOWLEDGE_INVALID_FILENAME")
        val type = mediaType.substringBefore(';').trim().lowercase()
        if (type !in setOf("application/pdf", "text/plain") ||
            (type == "application/pdf" && !filename.endsWith(".pdf", true)) ||
            (type == "text/plain" && !filename.endsWith(".txt", true))
        ) throw KnowledgeFailure("KNOWLEDGE_UNSUPPORTED_TYPE", 415)
        val (key, size) = store.store(input)
        var committed = false
        try {
            text.extract(store.path(key), type)
            val digest = MessageDigest.getInstance("SHA-256")
            Files.newInputStream(store.path(key)).use { source ->
                val bytes = ByteArray(8192)
                while (true) {
                    val n = source.read(bytes); if (n < 0) break; digest.update(bytes, 0, n)
                }
            }
            val id = UUID.randomUUID()
            repository.insert(
                actor,
                space,
                id,
                filename,
                type,
                key,
                size,
                digest.digest().joinToString("") { "%02x".format(it) })
            committed = true
            audit(actor, id, "knowledge.uploaded")
            return repository.find(actor, id)
        } finally {
            if (!committed) store.delete(key)
        }
    }

    fun delete(actor: UUID, id: UUID) {
        rbac.require(actor, "knowledge:delete"); repository.tombstone(actor, id)
        audit(actor, id, "knowledge.deleted")
    }

    fun search(actor: UUID, spaces: List<UUID>, query: String, limit: Int): List<KnowledgeSource> {
        rbac.require(actor, "knowledge:read")
        if (spaces.isEmpty() || spaces.size > 10 || spaces.distinct().size != spaces.size || query.isBlank() || query.length > 8000 || limit !in 1..5)
            throw KnowledgeFailure("INVALID_REQUEST")
        spaces.forEach { repository.requireSpace(actor, it) }
        val result = repository.search(
            actor,
            spaces,
            embeddings.embed(listOf(query)).single(),
            embeddings.modelId,
            embeddings.dimension,
            limit
        )
        audit(actor, UUID.randomUUID(), "knowledge.searched")
        return result
    }

    private fun audit(actor: UUID, correlation: UUID, event: String) = activity.record(
        ActivityCategory.SECURITY, event, ActivityStatus.SUCCEEDED, ActivityActorType.USER,
        "kyrion-core", event, actor.toString(), correlation, actor
    )
}

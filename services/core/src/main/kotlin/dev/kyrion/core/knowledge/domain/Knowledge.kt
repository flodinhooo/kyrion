package dev.kyrion.core.knowledge.domain

import java.time.Instant
import java.util.UUID

enum class KnowledgeOwnerType { PERSONAL, ORGANIZATION }
data class KnowledgeSpace(val id: UUID, val ownerType: KnowledgeOwnerType, val name: String)
data class KnowledgeDocument(
    val id: UUID, val spaceId: UUID, val originalFilename: String, val mediaType: String,
    val byteSize: Long, val status: String, val errorCode: String?, val ingestionRevision: Int,
    val createdAt: Instant,
)

data class KnowledgeSource(
    val documentId: UUID, val filename: String, val excerpt: String, val page: Int?,
    val startOffset: Int, val endOffset: Int, val reference: String,
)

data class KnowledgeChunk(val index: Int, val content: String, val page: Int?, val start: Int, val end: Int)
data class KnowledgeJob(
    val id: UUID, val documentId: UUID, val revision: Int, val lease: UUID,
    val storageKey: UUID, val mediaType: String, val owner: UUID
)

class KnowledgeFailure(val code: String, val status: Int = 400) : RuntimeException(code)

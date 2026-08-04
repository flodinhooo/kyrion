package dev.kyrion.core.conversation

import java.time.Instant
import java.util.UUID

data class ConversationSummary(val id: UUID, val title: String, val createdAt: Instant, val updatedAt: Instant)
data class ConversationMessage(val id: UUID, val role: String, val content: String, val createdAt: Instant)
data class Conversation(val id: UUID, val title: String, val createdAt: Instant, val updatedAt: Instant, val messages: List<ConversationMessage>)

data class ConversationContextMessage(val role: String, val content: String)

data class ConversationContext(
    val conversationId: UUID,
    val turnId: UUID,
    val messages: List<ConversationContextMessage>,
    val estimatedTokens: Int,
    val tokenBudget: Int,
    val compacted: Boolean,
)

enum class ConversationTurnStatus { started, completed, stopped, failed }

data class ConversationTurn(
    val id: UUID,
    val conversationId: UUID,
    val userMessageId: UUID,
    val assistantMessageId: UUID?,
    val status: ConversationTurnStatus,
    val errorCode: String?,
    val startedAt: Instant,
    val updatedAt: Instant,
)

data class ConversationContextSummary(
    val id: UUID,
    val conversationId: UUID,
    val sourceStartPosition: Int,
    val sourceEndPosition: Int,
    val algorithmVersion: Int,
    val content: String,
    val createdAt: Instant,
)

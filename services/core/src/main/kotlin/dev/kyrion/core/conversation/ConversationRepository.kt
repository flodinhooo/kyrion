package dev.kyrion.core.conversation

import java.util.UUID

interface ConversationRepository {
    fun replace(ownerId: UUID, conversation: Conversation): Conversation
    fun recent(ownerId: UUID, limit: Int): List<ConversationSummary>
    fun find(ownerId: UUID, id: UUID): Conversation?
    fun rename(ownerId: UUID, id: UUID, title: String, updatedAt: java.time.Instant): ConversationSummary?
    fun delete(ownerId: UUID, id: UUID): Boolean
    fun appendMessage(
        ownerId: UUID,
        conversationId: UUID,
        title: String,
        message: ConversationMessage,
        createIfMissing: Boolean,
        updatedAt: java.time.Instant,
    ): Conversation
    fun findContextSummary(
        conversationId: UUID,
        sourceStartPosition: Int,
        sourceEndPosition: Int,
        algorithmVersion: Int,
    ): ConversationContextSummary?
    fun saveContextSummary(summary: ConversationContextSummary): ConversationContextSummary
    fun startTurn(
        ownerId: UUID,
        conversationId: UUID,
        title: String,
        userMessage: ConversationMessage,
        startedAt: java.time.Instant,
    ): Conversation
    fun finishTurn(
        ownerId: UUID,
        conversationId: UUID,
        turnId: UUID,
        assistantMessage: ConversationMessage?,
        status: ConversationTurnStatus,
        errorCode: String?,
        updatedAt: java.time.Instant,
    ): Conversation
}

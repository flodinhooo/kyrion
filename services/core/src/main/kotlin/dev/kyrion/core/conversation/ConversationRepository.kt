package dev.kyrion.core.conversation

import java.util.UUID

interface ConversationRepository {
    fun replace(ownerId: UUID, conversation: Conversation): Conversation
    fun recent(ownerId: UUID, limit: Int): List<ConversationSummary>
    fun find(ownerId: UUID, id: UUID): Conversation?
    fun rename(ownerId: UUID, id: UUID, title: String, updatedAt: java.time.Instant): ConversationSummary?
    fun delete(ownerId: UUID, id: UUID): Boolean
}

package dev.kyrion.core.conversation

import java.time.Instant
import java.util.UUID

data class ConversationSummary(val id: UUID, val title: String, val createdAt: Instant, val updatedAt: Instant)
data class ConversationMessage(val id: UUID, val role: String, val content: String, val createdAt: Instant)
data class Conversation(val id: UUID, val title: String, val createdAt: Instant, val updatedAt: Instant, val messages: List<ConversationMessage>)

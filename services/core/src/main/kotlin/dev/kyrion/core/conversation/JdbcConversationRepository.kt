package dev.kyrion.core.conversation

import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.transaction.support.TransactionTemplate
import java.sql.ResultSet
import java.sql.Timestamp
import java.util.UUID

@Repository
class JdbcConversationRepository(private val jdbc: JdbcClient, private val transactions: TransactionTemplate) : ConversationRepository {
    override fun replace(ownerId: UUID, conversation: Conversation): Conversation = requireNotNull(transactions.execute {
        val updated = jdbc.sql(
            """INSERT INTO conversation (id, owner_id, title, created_at, updated_at)
               VALUES (:id, :ownerId, :title, :createdAt, :updatedAt)
               ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, updated_at = EXCLUDED.updated_at
               WHERE conversation.owner_id = EXCLUDED.owner_id""",
        ).param("id", conversation.id).param("ownerId", ownerId).param("title", conversation.title)
            .param("createdAt", Timestamp.from(conversation.createdAt)).param("updatedAt", Timestamp.from(conversation.updatedAt)).update()
        if (updated != 1) throw ConversationNotFoundException()
        jdbc.sql("DELETE FROM conversation_message WHERE conversation_id = :id").param("id", conversation.id).update()
        conversation.messages.forEachIndexed { position, message ->
            jdbc.sql("""INSERT INTO conversation_message (id, conversation_id, role, content, position, created_at)
                VALUES (:id, :conversationId, :role, :content, :position, :createdAt)""")
                .param("id", message.id).param("conversationId", conversation.id).param("role", message.role)
                .param("content", message.content).param("position", position).param("createdAt", Timestamp.from(message.createdAt)).update()
        }
        conversation
    })

    override fun recent(ownerId: UUID, limit: Int): List<ConversationSummary> = jdbc.sql(
        "SELECT id, title, created_at, updated_at FROM conversation WHERE owner_id = :ownerId ORDER BY updated_at DESC LIMIT :limit",
    ).param("ownerId", ownerId).param("limit", limit).query(::summary).list()

    override fun find(ownerId: UUID, id: UUID): Conversation? {
        val summary = jdbc.sql("SELECT id, title, created_at, updated_at FROM conversation WHERE id = :id AND owner_id = :ownerId")
            .param("id", id).param("ownerId", ownerId).query(::summary).optional().orElse(null) ?: return null
        val messages = jdbc.sql("SELECT id, role, content, created_at FROM conversation_message WHERE conversation_id = :id ORDER BY position")
            .param("id", id).query { rs, _ -> ConversationMessage(rs.getObject("id", UUID::class.java), rs.getString("role"), rs.getString("content"), rs.getTimestamp("created_at").toInstant()) }.list()
        return Conversation(summary.id, summary.title, summary.createdAt, summary.updatedAt, messages)
    }

    override fun rename(ownerId: UUID, id: UUID, title: String, updatedAt: java.time.Instant): ConversationSummary? {
        val updated = jdbc.sql(
            "UPDATE conversation SET title = :title, updated_at = :updatedAt WHERE id = :id AND owner_id = :ownerId",
        ).param("title", title).param("updatedAt", Timestamp.from(updatedAt)).param("id", id).param("ownerId", ownerId).update()
        return if (updated == 1) jdbc.sql(
            "SELECT id, title, created_at, updated_at FROM conversation WHERE id = :id AND owner_id = :ownerId",
        ).param("id", id).param("ownerId", ownerId).query(::summary).single() else null
    }

    override fun delete(ownerId: UUID, id: UUID): Boolean = jdbc.sql(
        "DELETE FROM conversation WHERE id = :id AND owner_id = :ownerId",
    ).param("id", id).param("ownerId", ownerId).update() == 1

    override fun appendMessage(
        ownerId: UUID,
        conversationId: UUID,
        title: String,
        message: ConversationMessage,
        createIfMissing: Boolean,
        updatedAt: java.time.Instant,
    ): Conversation = requireNotNull(transactions.execute {
        var existingOwner = jdbc.sql("SELECT owner_id FROM conversation WHERE id = :id FOR UPDATE")
            .param("id", conversationId).query(UUID::class.java).optional().orElse(null)
        if (existingOwner == null) {
            if (!createIfMissing) throw ConversationNotFoundException()
            jdbc.sql(
                """INSERT INTO conversation (id, owner_id, title, created_at, updated_at)
                   VALUES (:id, :ownerId, :title, :now, :now) ON CONFLICT (id) DO NOTHING""",
            ).param("id", conversationId).param("ownerId", ownerId).param("title", title)
                .param("now", Timestamp.from(updatedAt)).update()
            existingOwner = jdbc.sql("SELECT owner_id FROM conversation WHERE id = :id FOR UPDATE")
                .param("id", conversationId).query(UUID::class.java).single()
        }
        if (existingOwner != ownerId) throw ConversationNotFoundException()
        val duplicate = jdbc.sql("SELECT COUNT(*) FROM conversation_message WHERE id = :id")
            .param("id", message.id).query(Int::class.java).single() > 0
        if (duplicate) throw ConversationConflictException()
        val position = jdbc.sql(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM conversation_message WHERE conversation_id = :conversationId",
        ).param("conversationId", conversationId).query(Int::class.java).single()
        jdbc.sql(
            """INSERT INTO conversation_message (id, conversation_id, role, content, position, created_at)
               VALUES (:id, :conversationId, :role, :content, :position, :createdAt)""",
        ).param("id", message.id).param("conversationId", conversationId).param("role", message.role)
            .param("content", message.content).param("position", position)
            .param("createdAt", Timestamp.from(message.createdAt)).update()
        jdbc.sql("UPDATE conversation SET updated_at = :updatedAt WHERE id = :id AND owner_id = :ownerId")
            .param("updatedAt", Timestamp.from(updatedAt)).param("id", conversationId).param("ownerId", ownerId).update()
        find(ownerId, conversationId) ?: throw ConversationNotFoundException()
    })

    override fun findContextSummary(
        conversationId: UUID,
        sourceStartPosition: Int,
        sourceEndPosition: Int,
        algorithmVersion: Int,
    ): ConversationContextSummary? = jdbc.sql(
        """SELECT id, conversation_id, source_start_position, source_end_position,
                  algorithm_version, content, created_at
           FROM conversation_context_summary
           WHERE conversation_id = :conversationId
             AND source_start_position = :sourceStart
             AND source_end_position = :sourceEnd
             AND algorithm_version = :version""",
    ).param("conversationId", conversationId).param("sourceStart", sourceStartPosition)
        .param("sourceEnd", sourceEndPosition).param("version", algorithmVersion)
        .query { rs, _ -> contextSummary(rs) }.optional().orElse(null)

    override fun saveContextSummary(summary: ConversationContextSummary): ConversationContextSummary {
        jdbc.sql(
            """INSERT INTO conversation_context_summary
               (id, conversation_id, source_start_position, source_end_position, algorithm_version, content, created_at)
               VALUES (:id, :conversationId, :sourceStart, :sourceEnd, :version, :content, :createdAt)
               ON CONFLICT (conversation_id, source_start_position, source_end_position, algorithm_version) DO NOTHING""",
        ).param("id", summary.id).param("conversationId", summary.conversationId)
            .param("sourceStart", summary.sourceStartPosition).param("sourceEnd", summary.sourceEndPosition)
            .param("version", summary.algorithmVersion).param("content", summary.content)
            .param("createdAt", Timestamp.from(summary.createdAt)).update()
        return findContextSummary(
            summary.conversationId, summary.sourceStartPosition, summary.sourceEndPosition, summary.algorithmVersion,
        ) ?: error("Context summary was not persisted")
    }

    override fun startTurn(
        ownerId: UUID,
        conversationId: UUID,
        title: String,
        userMessage: ConversationMessage,
        startedAt: java.time.Instant,
    ): Conversation = requireNotNull(transactions.execute {
        val conversation = appendMessage(
            ownerId, conversationId, title, userMessage, createIfMissing = true, updatedAt = startedAt,
        )
        jdbc.sql(
            """INSERT INTO conversation_turn
               (id, conversation_id, user_message_id, status, started_at, updated_at)
               VALUES (:id, :conversationId, :userMessageId, 'started', :startedAt, :startedAt)""",
        ).param("id", userMessage.id).param("conversationId", conversationId)
            .param("userMessageId", userMessage.id).param("startedAt", Timestamp.from(startedAt)).update()
        conversation
    })

    override fun finishTurn(
        ownerId: UUID,
        conversationId: UUID,
        turnId: UUID,
        assistantMessage: ConversationMessage?,
        status: ConversationTurnStatus,
        errorCode: String?,
        updatedAt: java.time.Instant,
    ): Conversation = requireNotNull(transactions.execute {
        val currentStatus = jdbc.sql(
            """SELECT turn.status FROM conversation_turn turn
               JOIN conversation ON conversation.id = turn.conversation_id
               WHERE turn.id = :turnId AND turn.conversation_id = :conversationId
                 AND conversation.owner_id = :ownerId FOR UPDATE""",
        ).param("turnId", turnId).param("conversationId", conversationId).param("ownerId", ownerId)
            .query(String::class.java).optional().orElse(null) ?: throw ConversationNotFoundException()
        if (currentStatus != "started") throw ConversationConflictException()
        val conversation = if (assistantMessage != null) {
            appendMessage(
                ownerId, conversationId, "unused", assistantMessage,
                createIfMissing = false, updatedAt = updatedAt,
            )
        } else {
            find(ownerId, conversationId) ?: throw ConversationNotFoundException()
        }
        jdbc.sql(
            """UPDATE conversation_turn
               SET assistant_message_id = :assistantMessageId, status = :status,
                   error_code = :errorCode, updated_at = :updatedAt
               WHERE id = :turnId""",
        ).param("assistantMessageId", assistantMessage?.id).param("status", status.name)
            .param("errorCode", errorCode).param("updatedAt", Timestamp.from(updatedAt))
            .param("turnId", turnId).update()
        conversation
    })

    @Suppress("UNUSED_PARAMETER") private fun summary(rs: ResultSet, row: Int) = ConversationSummary(
        rs.getObject("id", UUID::class.java), rs.getString("title"), rs.getTimestamp("created_at").toInstant(), rs.getTimestamp("updated_at").toInstant(),
    )

    private fun contextSummary(rs: ResultSet) = ConversationContextSummary(
        rs.getObject("id", UUID::class.java), rs.getObject("conversation_id", UUID::class.java),
        rs.getInt("source_start_position"), rs.getInt("source_end_position"), rs.getInt("algorithm_version"),
        rs.getString("content"), rs.getTimestamp("created_at").toInstant(),
    )
}

class ConversationNotFoundException : RuntimeException()
class ConversationConflictException : RuntimeException()

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

    @Suppress("UNUSED_PARAMETER") private fun summary(rs: ResultSet, row: Int) = ConversationSummary(
        rs.getObject("id", UUID::class.java), rs.getString("title"), rs.getTimestamp("created_at").toInstant(), rs.getTimestamp("updated_at").toInstant(),
    )
}

class ConversationNotFoundException : RuntimeException()

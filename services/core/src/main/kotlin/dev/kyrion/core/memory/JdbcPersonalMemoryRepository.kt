package dev.kyrion.core.memory

import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import java.sql.ResultSet
import java.sql.Timestamp
import java.time.Instant
import java.util.UUID

@Repository
class JdbcPersonalMemoryRepository(private val jdbc: JdbcClient) : PersonalMemoryRepository {
    override fun settings(ownerId: UUID): MemorySettings = jdbc.sql(
        "SELECT enabled, updated_at FROM owner_memory_settings WHERE owner_id = :ownerId",
    ).param("ownerId", ownerId).query { rs, _ -> MemorySettings(rs.getBoolean("enabled"), rs.getTimestamp("updated_at").toInstant()) }
        .optional().orElse(MemorySettings(false, null))

    override fun updateSettings(ownerId: UUID, enabled: Boolean, updatedAt: Instant): MemorySettings {
        jdbc.sql(
            """INSERT INTO owner_memory_settings (owner_id, enabled, updated_at)
               VALUES (:ownerId, :enabled, :updatedAt)
               ON CONFLICT (owner_id) DO UPDATE SET enabled = EXCLUDED.enabled, updated_at = EXCLUDED.updated_at""",
        ).param("ownerId", ownerId).param("enabled", enabled).param("updatedAt", Timestamp.from(updatedAt)).update()
        return MemorySettings(enabled, updatedAt)
    }

    override fun recent(ownerId: UUID, limit: Int): List<PersonalMemory> = jdbc.sql(
        """SELECT * FROM personal_memory WHERE owner_id = :ownerId
           ORDER BY updated_at DESC LIMIT :limit""",
    ).param("ownerId", ownerId).param("limit", limit).query { rs, _ -> memory(rs) }.list()

    override fun create(ownerId: UUID, memory: PersonalMemory): PersonalMemory {
        jdbc.sql(
            """INSERT INTO personal_memory
               (id, owner_id, category, content, sensitivity, origin, status, source_conversation_id,
                source_message_id, created_at, updated_at, confirmed_at)
               VALUES (:id, :ownerId, :category, :content, :sensitivity, :origin, :status,
                       :sourceConversationId, :sourceMessageId, :createdAt, :updatedAt, :confirmedAt)""",
        ).param("id", memory.id).param("ownerId", ownerId).param("category", memory.category.name)
            .param("content", memory.content).param("sensitivity", memory.sensitivity.name)
            .param("origin", memory.origin).param("status", memory.status.name)
            .param("sourceConversationId", memory.sourceConversationId).param("sourceMessageId", memory.sourceMessageId)
            .param("createdAt", Timestamp.from(memory.createdAt)).param("updatedAt", Timestamp.from(memory.updatedAt))
            .param("confirmedAt", memory.confirmedAt?.let(Timestamp::from)).update()
        return memory
    }

    override fun find(ownerId: UUID, id: UUID): PersonalMemory? = jdbc.sql(
        "SELECT * FROM personal_memory WHERE id = :id AND owner_id = :ownerId",
    ).param("id", id).param("ownerId", ownerId).query { rs, _ -> memory(rs) }.optional().orElse(null)

    override fun confirm(ownerId: UUID, id: UUID, confirmedAt: Instant): PersonalMemory? {
        jdbc.sql(
            """UPDATE personal_memory SET status = 'confirmed', confirmed_at = :confirmedAt, updated_at = :confirmedAt
               WHERE id = :id AND owner_id = :ownerId AND status = 'proposed'""",
        ).param("confirmedAt", Timestamp.from(confirmedAt)).param("id", id).param("ownerId", ownerId).update()
        return find(ownerId, id)
    }

    override fun update(
        ownerId: UUID,
        id: UUID,
        category: MemoryCategory,
        content: String,
        sensitivity: MemorySensitivity,
        updatedAt: Instant,
    ): PersonalMemory? {
        val updated = jdbc.sql(
            """UPDATE personal_memory SET category = :category, content = :content,
               sensitivity = :sensitivity, updated_at = :updatedAt WHERE id = :id AND owner_id = :ownerId""",
        ).param("category", category.name).param("content", content).param("sensitivity", sensitivity.name)
            .param("updatedAt", Timestamp.from(updatedAt)).param("id", id).param("ownerId", ownerId).update()
        return if (updated == 1) find(ownerId, id) else null
    }

    override fun delete(ownerId: UUID, id: UUID): Boolean = jdbc.sql(
        "DELETE FROM personal_memory WHERE id = :id AND owner_id = :ownerId",
    ).param("id", id).param("ownerId", ownerId).update() == 1

    private fun memory(rs: ResultSet) = PersonalMemory(
        rs.getObject("id", UUID::class.java), MemoryCategory.valueOf(rs.getString("category")),
        rs.getString("content"), MemorySensitivity.valueOf(rs.getString("sensitivity")),
        rs.getString("origin"), MemoryStatus.valueOf(rs.getString("status")),
        rs.getObject("source_conversation_id", UUID::class.java), rs.getObject("source_message_id", UUID::class.java),
        rs.getTimestamp("created_at").toInstant(), rs.getTimestamp("updated_at").toInstant(),
        rs.getTimestamp("confirmed_at")?.toInstant(),
    )
}

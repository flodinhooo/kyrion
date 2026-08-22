package dev.kyrion.core.activity

import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.transaction.support.TransactionTemplate
import java.sql.ResultSet
import java.sql.Timestamp

@Repository
class JdbcActivityEventRepository(
    private val jdbcClient: JdbcClient,
    private val transactions: TransactionTemplate,
    private val integrity: ActivityIntegrity,
) : ActivityEventRepository {
    override fun append(event: ActivityEvent): ActivityEvent = transactions.execute {
        val scope = event.ownerId?.toString() ?: SYSTEM_SCOPE
        jdbcClient.sql("""INSERT INTO activity_integrity_chain(chain_scope,anchor_mac,updated_at) VALUES(:scope,:anchorMac,CURRENT_TIMESTAMP)
            ON CONFLICT(chain_scope) DO NOTHING""")
            .param("scope", scope).param("anchorMac", integrity.anchorMac(scope, null)).update()
        val previousHash = jdbcClient.sql("SELECT last_hash FROM activity_integrity_chain WHERE chain_scope=:scope FOR UPDATE")
            .param("scope", scope).query(ByteArray::class.java).optional().orElse(null)
        val eventHash = integrity.eventHash(event, scope, previousHash)
        jdbcClient.sql(
            """
            INSERT INTO activity_event (
                id, occurred_at, category, event_type, status, actor_type,
                actor_id, source, correlation_id, summary_code, owner_id,
                integrity_version, chain_scope, previous_hash, event_hash
            ) VALUES (
                :id, :occurredAt, :category, :eventType, :status, :actorType,
                :actorId, :source, :correlationId, :summaryCode, :ownerId,
                1, :chainScope, :previousHash, :eventHash
            )
            """.trimIndent(),
        )
            .param("id", event.id)
            .param("occurredAt", Timestamp.from(event.occurredAt))
            .param("category", event.category.name)
            .param("eventType", event.eventType)
            .param("status", event.status.name)
            .param("actorType", event.actorType.name)
            .param("actorId", event.actorId)
            .param("source", event.source)
            .param("correlationId", event.correlationId)
            .param("summaryCode", event.summaryCode)
            .param("ownerId", event.ownerId)
            .param("chainScope", scope)
            .param("previousHash", previousHash)
            .param("eventHash", eventHash)
            .update()
        jdbcClient.sql("UPDATE activity_integrity_chain SET last_event_id=:eventId,last_hash=:eventHash,updated_at=CURRENT_TIMESTAMP WHERE chain_scope=:scope")
            .param("eventId", event.id).param("eventHash", eventHash).param("scope", scope).update()
        event
    }

    override fun findRecent(limit: Int): List<ActivityEvent> = jdbcClient.sql(
        """
        SELECT id, occurred_at, category, event_type, status, actor_type,
               actor_id, source, correlation_id, summary_code
        FROM activity_event
        ORDER BY occurred_at DESC, id DESC
        LIMIT :limit
        """.trimIndent(),
    )
        .param("limit", limit)
        .query(::mapEvent)
        .list()

    override fun findRecentForOwner(ownerId: java.util.UUID, limit: Int): List<ActivityEvent> = jdbcClient.sql(
        """
        SELECT id, occurred_at, category, event_type, status, actor_type,
               actor_id, source, correlation_id, summary_code, owner_id
        FROM activity_event
        WHERE owner_id = :ownerId
           OR (owner_id IS NULL AND category = 'SYSTEM' AND actor_type = 'SYSTEM')
        ORDER BY occurred_at DESC, id DESC
        LIMIT :limit
        """.trimIndent(),
    )
        .param("ownerId", ownerId)
        .param("limit", limit)
        .query(::mapEvent)
        .list()

    @Suppress("UNUSED_PARAMETER")
    private fun mapEvent(resultSet: ResultSet, rowNumber: Int): ActivityEvent {
        return ActivityEvent(
            id = resultSet.getObject("id", java.util.UUID::class.java),
            occurredAt = resultSet.getTimestamp("occurred_at").toInstant(),
            category = ActivityCategory.valueOf(resultSet.getString("category")),
            eventType = resultSet.getString("event_type"),
            status = ActivityStatus.valueOf(resultSet.getString("status")),
            actorType = ActivityActorType.valueOf(resultSet.getString("actor_type")),
            actorId = resultSet.getString("actor_id"),
            source = resultSet.getString("source"),
            correlationId = resultSet.getObject("correlation_id", java.util.UUID::class.java),
            summaryCode = resultSet.getString("summary_code"),
            ownerId = runCatching { resultSet.getObject("owner_id", java.util.UUID::class.java) }.getOrNull(),
        )
    }
}

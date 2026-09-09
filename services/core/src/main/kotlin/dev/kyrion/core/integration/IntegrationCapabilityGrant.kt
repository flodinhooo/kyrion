package dev.kyrion.core.integration

import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import java.sql.Timestamp
import java.time.Instant
import java.util.UUID

data class IntegrationCapabilityGrant(val ownerId: UUID, val connectionId: UUID, val capability: String, val granted: Boolean, val createdAt: Instant, val updatedAt: Instant)

@Repository
class JdbcIntegrationCapabilityGrantRepository(private val jdbc: JdbcClient) {
    fun findAll(ownerId: UUID, connectionId: UUID): List<IntegrationCapabilityGrant> = jdbc.sql("SELECT * FROM integration_connection_capability WHERE owner_id=:ownerId AND connection_id=:connectionId ORDER BY capability").param("ownerId", ownerId).param("connectionId", connectionId).query { rs, _ -> IntegrationCapabilityGrant(ownerId, connectionId, rs.getString("capability"), rs.getBoolean("granted"), rs.getTimestamp("created_at").toInstant(), rs.getTimestamp("updated_at").toInstant()) }.list()
    fun replace(ownerId: UUID, connectionId: UUID, capabilities: Set<String>, now: Instant) {
        jdbc.sql("DELETE FROM integration_connection_capability WHERE owner_id=:ownerId AND connection_id=:connectionId").param("ownerId", ownerId).param("connectionId", connectionId).update()
        capabilities.forEach { jdbc.sql("INSERT INTO integration_connection_capability(owner_id,connection_id,capability,granted,created_at,updated_at) VALUES(:ownerId,:connectionId,:capability,true,:now,:now)").param("ownerId", ownerId).param("connectionId", connectionId).param("capability", it).param("now", Timestamp.from(now)).update() }
    }
    fun delete(ownerId: UUID, connectionId: UUID) = jdbc.sql("DELETE FROM integration_connection_capability WHERE owner_id=:ownerId AND connection_id=:connectionId").param("ownerId", ownerId).param("connectionId", connectionId).update()
}

package dev.kyrion.core.integration

import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import java.sql.ResultSet
import java.sql.Timestamp
import java.util.UUID

@Repository
class JdbcIntegrationConnectionRepository(private val jdbc: JdbcClient) : IntegrationConnectionRepository {
    override fun findAll(ownerId: UUID): List<IntegrationConnection> = jdbc.sql(
        "SELECT * FROM integration_connection WHERE owner_id = :ownerId ORDER BY created_at DESC",
    ).param("ownerId", ownerId).query { rs, _ -> connection(rs) }.list()

    override fun find(ownerId: UUID, id: UUID): IntegrationConnection? = jdbc.sql(
        "SELECT * FROM integration_connection WHERE owner_id = :ownerId AND id = :id",
    ).param("ownerId", ownerId).param("id", id).query { rs, _ -> connection(rs) }.optional().orElse(null)

    override fun save(connection: IntegrationConnection): IntegrationConnection {
        jdbc.sql(
            """INSERT INTO integration_connection
               (id, owner_id, provider, display_name, endpoint_host, credential_ciphertext, credential_nonce,
                credential_version, created_at, updated_at, device_class)
               VALUES (:id, :ownerId, :provider, :displayName, :endpointHost, :ciphertext, :nonce, :version, :createdAt, :updatedAt, :deviceClass)""",
        ).param("id", connection.id).param("ownerId", connection.ownerId).param("provider", connection.provider)
            .param("displayName", connection.displayName).param("endpointHost", connection.endpointHost)
            .param("ciphertext", connection.credentialCiphertext).param("nonce", connection.credentialNonce)
            .param("version", connection.credentialVersion).param("createdAt", Timestamp.from(connection.createdAt))
            .param("updatedAt", Timestamp.from(connection.updatedAt)).param("deviceClass", connection.deviceClass.value).update()
        return connection
    }

    override fun update(ownerId: UUID, id: UUID, displayName: String, deviceClass: DeviceClass, updatedAt: java.time.Instant): IntegrationConnection? {
        val updated = jdbc.sql("UPDATE integration_connection SET display_name=:displayName, device_class=:deviceClass, updated_at=:updatedAt WHERE owner_id=:ownerId AND id=:id")
            .param("displayName", displayName).param("deviceClass", deviceClass.value).param("updatedAt", Timestamp.from(updatedAt))
            .param("ownerId", ownerId).param("id", id).update()
        return if (updated == 1) find(ownerId, id) else null
    }

    override fun rename(ownerId: UUID, id: UUID, displayName: String, updatedAt: java.time.Instant): IntegrationConnection? {
        val updated = jdbc.sql("UPDATE integration_connection SET display_name = :displayName, updated_at = :updatedAt WHERE owner_id = :ownerId AND id = :id")
            .param("displayName", displayName).param("updatedAt", Timestamp.from(updatedAt)).param("ownerId", ownerId).param("id", id).update()
        return if (updated == 1) find(ownerId, id) else null
    }

    override fun delete(ownerId: UUID, id: UUID): Boolean = jdbc.sql(
        "DELETE FROM integration_connection WHERE owner_id = :ownerId AND id = :id",
    ).param("ownerId", ownerId).param("id", id).update() == 1

    private fun connection(rs: ResultSet) = IntegrationConnection(
        rs.getObject("id", UUID::class.java), rs.getObject("owner_id", UUID::class.java), rs.getString("provider"),
        rs.getString("display_name"), rs.getString("endpoint_host"), rs.getBytes("credential_ciphertext"),
        rs.getBytes("credential_nonce"), rs.getInt("credential_version"), rs.getTimestamp("created_at").toInstant(),
        rs.getTimestamp("updated_at").toInstant(), rs.getObject("room_id", UUID::class.java),
        DeviceClass.entries.single { it.value == rs.getString("device_class") },
    )
}

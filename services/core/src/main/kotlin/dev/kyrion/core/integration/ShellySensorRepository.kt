package dev.kyrion.core.integration

import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import java.sql.Timestamp
import java.time.Instant
import java.util.UUID

data class StoredShellyReading(val connectionId: UUID, val ownerId: UUID, val reading: ShellySensorReading, val observedAt: Instant)

interface ShellySensorRepository {
    fun all(ownerId: UUID): List<StoredShellyReading>
    fun save(value: StoredShellyReading)
}

@Repository
class JdbcShellySensorRepository(private val jdbc: JdbcClient) : ShellySensorRepository {
    override fun all(ownerId: UUID): List<StoredShellyReading> = jdbc.sql(
        "SELECT * FROM shelly_sensor_reading WHERE owner_id = :ownerId",
    ).param("ownerId", ownerId).query { rs, _ ->
        StoredShellyReading(rs.getObject("connection_id", UUID::class.java), ownerId,
            ShellySensorReading(rs.getObject("temperature_celsius", Double::class.javaObjectType),
                rs.getObject("relative_humidity", Double::class.javaObjectType),
                rs.getObject("battery", Double::class.javaObjectType)), rs.getTimestamp("observed_at").toInstant())
    }.list()

    override fun save(value: StoredShellyReading) {
        jdbc.sql("""INSERT INTO shelly_sensor_reading (connection_id, owner_id, temperature_celsius, relative_humidity, battery, observed_at)
            VALUES (:id, :owner, :temperature, :humidity, :battery, :observed)
            ON CONFLICT (connection_id) DO UPDATE SET temperature_celsius=EXCLUDED.temperature_celsius,
            relative_humidity=EXCLUDED.relative_humidity, battery=EXCLUDED.battery, observed_at=EXCLUDED.observed_at
            WHERE shelly_sensor_reading.owner_id=EXCLUDED.owner_id""")
            .param("id", value.connectionId).param("owner", value.ownerId)
            .param("temperature", value.reading.temperatureCelsius, java.sql.Types.DOUBLE)
            .param("humidity", value.reading.relativeHumidity, java.sql.Types.DOUBLE)
            .param("battery", value.reading.battery, java.sql.Types.DOUBLE)
            .param("observed", Timestamp.from(value.observedAt)).update()
    }
}

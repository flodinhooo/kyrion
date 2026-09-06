package dev.kyrion.core.automation

import dev.kyrion.core.capability.DeviceCatalogService
import dev.kyrion.core.gateway.GatewayNode
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.security.workspaceOwnerId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController
import java.sql.Timestamp
import java.time.Clock
import java.time.Instant
import java.util.UUID

data class ZigbeeMotionEvent(val id: UUID, val detected: Boolean, val occurredAt: Instant)

@Repository
class ZigbeeMotionEventRepository(private val jdbc: JdbcClient) {
    fun recent(ownerId: UUID, sensorId: UUID, limit: Int = 12): List<ZigbeeMotionEvent> = jdbc.sql(
        """SELECT id, detected, occurred_at FROM zigbee_motion_event
           WHERE owner_id=:ownerId AND sensor_connection_id=:sensorId
           ORDER BY occurred_at DESC LIMIT :limit""",
    ).param("ownerId", ownerId).param("sensorId", sensorId).param("limit", limit)
        .query { rs, _ -> ZigbeeMotionEvent(rs.getObject("id", UUID::class.java), rs.getBoolean("detected"), rs.getTimestamp("occurred_at").toInstant()) }
        .list()

    fun appendIfChanged(ownerId: UUID, sensorId: UUID, detected: Boolean, occurredAt: Instant) {
        val previous = recent(ownerId, sensorId, 1).firstOrNull()
        if (previous?.detected == detected) return
        jdbc.sql(
            """INSERT INTO zigbee_motion_event (id, owner_id, sensor_connection_id, detected, occurred_at)
               VALUES (:id, :ownerId, :sensorId, :detected, :occurredAt)""",
        ).param("id", UUID.randomUUID()).param("ownerId", ownerId).param("sensorId", sensorId)
            .param("detected", detected).param("occurredAt", Timestamp.from(occurredAt)).update()
    }
}

@Service
class ZigbeeMotionEventService(
    private val repository: ZigbeeMotionEventRepository,
    private val connections: IntegrationConnectionRepository,
    private val catalog: DeviceCatalogService,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun record(node: GatewayNode, ieeeAddress: String, detected: Boolean) {
        val sensor = connections.findAll(node.ownerId).singleOrNull {
            it.provider == "zigbee" && it.endpointHost == ieeeAddress
        } ?: throw ZigbeeButtonBindingInvalidException()
        requireSensor(node.ownerId, sensor.id)
        repository.appendIfChanged(node.ownerId, sensor.id, detected, clock.instant())
    }

    fun recent(ownerId: UUID, sensorId: UUID): List<ZigbeeMotionEvent> {
        requireSensor(ownerId, sensorId)
        return repository.recent(ownerId, sensorId)
    }

    private fun requireSensor(ownerId: UUID, sensorId: UUID) {
        val sensor = catalog.devices(ownerId).singleOrNull { it.id == sensorId }
        if (sensor?.provider != "zigbee" || sensor.capabilities.none { it.id == "occupancy.read" }) {
            throw ZigbeeButtonBindingInvalidException()
        }
    }
}

@RestController
@RequestMapping("/v1/devices/{sensorId}/motion-events")
class ZigbeeMotionEventController(private val service: ZigbeeMotionEventService) {
    @GetMapping
    fun recent(@PathVariable sensorId: UUID, request: HttpServletRequest) =
        service.recent(request.ownerId(), sensorId)

    private fun HttpServletRequest.ownerId() = workspaceOwnerId()
}

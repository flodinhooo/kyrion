package dev.kyrion.core.capability

import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.NanoleafIntegrationService
import dev.kyrion.core.integration.NanoleafInvalidResponseException
import dev.kyrion.core.integration.NanoleafUnavailableException
import dev.kyrion.core.gateway.GatewayService
import dev.kyrion.core.gateway.ZigbeeDeviceSyncService
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import java.sql.Timestamp
import java.time.Clock
import java.time.Instant
import java.util.UUID

data class DeviceObservation(
    val connectionId: UUID,
    val ownerId: UUID,
    val availability: DeviceAvailability,
    val observedAt: Instant,
)

interface DeviceObservationRepository {
    fun findAll(ownerId: UUID): List<DeviceObservation>
    fun save(observation: DeviceObservation): DeviceObservation
}

interface DeviceProviderObserver {
    val provider: String
    fun observe(ownerId: UUID, connection: IntegrationConnection): DeviceAvailability
}

@Service
class NanoleafDeviceProviderObserver(
    private val nanoleaf: NanoleafIntegrationService,
) : DeviceProviderObserver {
    override val provider = NanoleafIntegrationService.PROVIDER

    override fun observe(ownerId: UUID, connection: IntegrationConnection): DeviceAvailability = try {
        nanoleaf.state(ownerId, connection.id)
        DeviceAvailability.ONLINE
    } catch (_: NanoleafUnavailableException) {
        DeviceAvailability.OFFLINE
    } catch (_: NanoleafInvalidResponseException) {
        DeviceAvailability.DEGRADED
    } catch (_: RuntimeException) {
        DeviceAvailability.DEGRADED
    }
}

@Service
class ZigbeeDeviceProviderObserver(
    private val gateways: GatewayService,
) : DeviceProviderObserver {
    override val provider = ZigbeeDeviceSyncService.PROVIDER

    override fun observe(ownerId: UUID, connection: IntegrationConnection): DeviceAvailability {
        val gateway = gateways.all(ownerId).firstOrNull { node ->
            node.health?.zigbee?.devices?.any { it.ieeeAddress == connection.endpointHost } == true
        } ?: return DeviceAvailability.OFFLINE
        return when (gateway.availability) {
            "online" -> DeviceAvailability.ONLINE
            "degraded" -> DeviceAvailability.DEGRADED
            "offline" -> DeviceAvailability.OFFLINE
            else -> DeviceAvailability.UNKNOWN
        }
    }
}

@Repository
class JdbcDeviceObservationRepository(private val jdbc: JdbcClient) : DeviceObservationRepository {
    override fun findAll(ownerId: UUID): List<DeviceObservation> = jdbc.sql(
        "SELECT * FROM device_observation WHERE owner_id = :ownerId",
    ).param("ownerId", ownerId).query { rs, _ ->
        DeviceObservation(
            rs.getObject("connection_id", UUID::class.java),
            rs.getObject("owner_id", UUID::class.java),
            DeviceAvailability.entries.single { it.value == rs.getString("availability") },
            rs.getTimestamp("observed_at").toInstant(),
        )
    }.list()

    override fun save(observation: DeviceObservation): DeviceObservation {
        jdbc.sql(
            """INSERT INTO device_observation (connection_id, owner_id, availability, observed_at)
               VALUES (:connectionId, :ownerId, :availability, :observedAt)
               ON CONFLICT (connection_id) DO UPDATE
               SET availability = EXCLUDED.availability, observed_at = EXCLUDED.observed_at
               WHERE device_observation.owner_id = EXCLUDED.owner_id""",
        ).param("connectionId", observation.connectionId)
            .param("ownerId", observation.ownerId)
            .param("availability", observation.availability.value)
            .param("observedAt", Timestamp.from(observation.observedAt))
            .update()
        return observation
    }
}

@Service
class DeviceObservationService(
    private val connections: IntegrationConnectionRepository,
    private val observations: DeviceObservationRepository,
    providerObservers: List<DeviceProviderObserver>,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
) {
    private val providerObservers = providerObservers.associateBy { it.provider }

    fun refresh(ownerId: UUID): List<DeviceObservation> {
        val correlationId = UUID.randomUUID()
        val refreshed = connections.findAll(ownerId).take(MAX_REFRESH_DEVICES).mapNotNull { connection ->
            val observer = providerObservers[connection.provider] ?: return@mapNotNull null
            val availability = observer.observe(ownerId, connection)
            observations.save(DeviceObservation(connection.id, ownerId, availability, clock.instant()))
        }
        activity.record(
            ActivityCategory.CAPABILITY,
            "capability.device.observations.refreshed",
            ActivityStatus.SUCCEEDED,
            ActivityActorType.USER,
            "kyrion-core",
            "device.observations.refreshed",
            ownerId.toString(),
            correlationId,
        )
        return refreshed
    }

    companion object {
        const val MAX_REFRESH_DEVICES = 20
    }
}

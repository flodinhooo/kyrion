package dev.kyrion.core.integration

import dev.kyrion.core.activity.*
import dev.kyrion.core.capability.*
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.time.Clock
import java.util.UUID

@Service
class ShellyIntegrationService(
    private val connections: IntegrationConnectionRepository,
    private val readings: ShellySensorRepository,
    private val observations: DeviceObservationRepository,
    private val gateway: ShellyGateway,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
) : DeviceProviderObserver {
    override val provider = "shelly"

    @Transactional
    fun connect(ownerId: UUID, host: String, displayName: String?, confirmed: Boolean): IntegrationConnectionView {
        if (!confirmed) throw IntegrationConfirmationRequiredException()
        val address = privateNetworkIpv4(host)
        val name = displayName?.trim()?.takeIf { it.isNotBlank() } ?: "Shelly H&T"
        if (name.length > 160) throw IntegrationInvalidNameException()
        val reading = gateway.read(address)
        val now = clock.instant()
        val existing = connections.findAll(ownerId).firstOrNull { it.provider == provider && it.endpointHost == address }
        val connection = existing ?: connections.save(IntegrationConnection(
            UUID.randomUUID(), ownerId, provider, name, address, byteArrayOf(), byteArrayOf(), 1, now, now,
            deviceClass = DeviceClass.SENSOR,
        ))
        readings.save(StoredShellyReading(connection.id, ownerId, reading, now))
        observations.save(DeviceObservation(connection.id, ownerId, DeviceAvailability.ONLINE, now))
        activity.record(ActivityCategory.INTEGRATION, "integration.shelly.connected", ActivityStatus.SUCCEEDED,
            ActivityActorType.USER, "kyrion-core", "shelly.connected", ownerId.toString(), UUID.randomUUID())
        return connection.view()
    }

    override fun observe(ownerId: UUID, connection: IntegrationConnection): DeviceAvailability {
        val owned = connections.find(ownerId, connection.id)?.takeIf { it.provider == provider }
            ?: throw IntegrationNotFoundException()
        return try {
            val reading = gateway.read(owned.endpointHost)
            readings.save(StoredShellyReading(owned.id, ownerId, reading, clock.instant()))
            DeviceAvailability.ONLINE
        } catch (exception: ShellyException) {
            // A sleeping sensor is not evidence of an offline device; preserve its last reading.
            if (exception.code == "SHELLY_UNAVAILABLE") DeviceAvailability.UNKNOWN else DeviceAvailability.DEGRADED
        }
    }
}

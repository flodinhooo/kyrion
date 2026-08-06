package dev.kyrion.core.gateway

import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.capability.DeviceAvailability
import dev.kyrion.core.capability.DeviceObservation
import dev.kyrion.core.capability.DeviceObservationRepository
import org.springframework.stereotype.Service
import java.time.Clock
import java.util.UUID

@Service
class ZigbeeDeviceSyncService(
    private val connections: IntegrationConnectionRepository,
    private val observations: DeviceObservationRepository,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun sync(node: GatewayNode, health: GatewayHealth) {
        val devices = health.zigbee?.devices.orEmpty().filter { it.supported }
        if (devices.isEmpty()) return
        val existing = connections.findAll(node.ownerId)
            .filter { it.provider == PROVIDER }.associateBy { it.endpointHost }
        val now = clock.instant()
        devices.forEach { device ->
            val connection = existing[device.ieeeAddress] ?: connections.save(
                IntegrationConnection(
                    UUID.randomUUID(), node.ownerId, PROVIDER,
                    listOf(device.vendor, device.description).filter(String::isNotBlank).joinToString(" ").take(160),
                    device.ieeeAddress, byteArrayOf(), byteArrayOf(), 1, now, now,
                ),
            )
            observations.save(DeviceObservation(connection.id, node.ownerId, DeviceAvailability.ONLINE, now))
        }
    }

    companion object { const val PROVIDER = "zigbee" }
}

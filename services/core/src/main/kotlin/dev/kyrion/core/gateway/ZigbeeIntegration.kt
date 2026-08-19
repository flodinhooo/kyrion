package dev.kyrion.core.gateway

import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.capability.DeviceAvailability
import dev.kyrion.core.capability.DeviceObservation
import dev.kyrion.core.capability.DeviceObservationRepository
import org.springframework.stereotype.Service
import java.time.Clock
import java.util.UUID
import dev.kyrion.core.integration.IntegrationConnectionView
import dev.kyrion.core.integration.view
import dev.kyrion.core.integration.DeviceClass

@Service
class ZigbeeDeviceSyncService(
    private val connections: IntegrationConnectionRepository,
    private val observations: DeviceObservationRepository,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun candidates(ownerId: UUID, nodeId: UUID, commands: GatewayCommandService): List<GatewayZigbeeDevice> {
        val node = commands.gateway(ownerId, nodeId)
        val approved = connections.findAll(ownerId).asSequence()
            .filter { it.provider == PROVIDER }.map { it.endpointHost }.toSet()
        return node.health?.zigbee?.devices.orEmpty().filter {
            it.supported && it.ieeeAddress !in approved
        }
    }

    fun add(ownerId: UUID, nodeId: UUID, ieeeAddress: String, displayName: String, deviceClass: DeviceClass, commands: GatewayCommandService): IntegrationConnectionView {
        val node = commands.gateway(ownerId, nodeId)
        val device = node.health?.zigbee?.devices?.singleOrNull {
            it.ieeeAddress == ieeeAddress && it.supported
        } ?: throw GatewayCommandInvalidException()
        val now = clock.instant()
        val existing = connections.findAll(ownerId).singleOrNull {
            it.provider == PROVIDER && it.endpointHost == ieeeAddress
        }
        val name = displayName.trim()
        val connection = if (existing == null) {
            connections.save(IntegrationConnection(
                UUID.randomUUID(), ownerId, PROVIDER, name, ieeeAddress,
                byteArrayOf(), byteArrayOf(), 1, now, now, deviceClass = deviceClass,
            ))
        } else {
            connections.update(ownerId, existing.id, name, deviceClass, now) ?: throw GatewayCommandInvalidException()
        }
        if (device.vendor.contains("Philips", ignoreCase = true) || device.vendor.contains("Signify", ignoreCase = true)) {
            commands.enqueue(ownerId, nodeId, "zigbee.hue_power_on_recover", mapOf("deviceId" to ieeeAddress))
        }
        observations.save(DeviceObservation(connection.id, ownerId, DeviceAvailability.ONLINE, now))
        return connection.view()
    }

    fun sync(node: GatewayNode, health: GatewayHealth) {
        val devices = health.zigbee?.devices.orEmpty().filter { it.supported }
        val existing = connections.findAll(node.ownerId)
            .filter { it.provider == PROVIDER }.associateBy { it.endpointHost }
        val now = clock.instant()
        devices.forEach { device ->
            existing[device.ieeeAddress]?.let { connection ->
                observations.save(DeviceObservation(connection.id, node.ownerId, DeviceAvailability.ONLINE, now))
            }
        }
    }

    companion object { const val PROVIDER = "zigbee" }
}

package dev.kyrion.core.gateway

import dev.kyrion.core.capability.DeviceAvailability
import dev.kyrion.core.capability.DeviceObservation
import dev.kyrion.core.capability.DeviceObservationRepository
import dev.kyrion.core.integration.DeviceClass
import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.integration.IntegrationConnectionView
import dev.kyrion.core.integration.view
import org.springframework.stereotype.Service
import java.time.Clock
import java.util.UUID

@Service
class BluetoothDeviceSyncService(
    private val connections: IntegrationConnectionRepository,
    private val observations: DeviceObservationRepository,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun candidates(ownerId: UUID, nodeId: UUID, commands: GatewayCommandService): List<GatewayBluetoothDevice> {
        val node = commands.gateway(ownerId, nodeId)
        val approved = connections.findAll(ownerId).asSequence()
            .filter { it.provider == PROVIDER }.map { it.endpointHost }.toSet()
        return node.health?.bluetoothDevices.orEmpty().filter { it.supported && it.address !in approved }
    }

    fun add(
        ownerId: UUID,
        nodeId: UUID,
        address: String,
        displayName: String,
        commands: GatewayCommandService,
    ): IntegrationConnectionView {
        val node = commands.gateway(ownerId, nodeId)
        val device = node.health?.bluetoothDevices?.singleOrNull {
            it.address == address && it.supported
        } ?: throw GatewayCommandInvalidException()
        val now = clock.instant()
        val existing = connections.findAll(ownerId).singleOrNull {
            it.provider == PROVIDER && it.endpointHost == address
        }
        val name = displayName.trim()
        val connection = existing ?: connections.save(IntegrationConnection(
            UUID.randomUUID(), ownerId, PROVIDER, name, address,
            byteArrayOf(), byteArrayOf(), 1, now, now, deviceClass = DeviceClass.LIGHT,
        ))
        observations.save(DeviceObservation(connection.id, ownerId, DeviceAvailability.ONLINE, now))
        return connection.view()
    }

    fun sync(node: GatewayNode, health: GatewayHealth) {
        val available = health.bluetoothDevices.filter { it.supported }.map { it.address }.toSet()
        val now = clock.instant()
        connections.findAll(node.ownerId).filter { it.provider == PROVIDER }.forEach { connection ->
            val availability = if (connection.endpointHost in available) {
                DeviceAvailability.ONLINE
            } else {
                DeviceAvailability.OFFLINE
            }
            observations.save(DeviceObservation(connection.id, node.ownerId, availability, now))
        }
    }

    companion object { const val PROVIDER = "bluetooth" }
}

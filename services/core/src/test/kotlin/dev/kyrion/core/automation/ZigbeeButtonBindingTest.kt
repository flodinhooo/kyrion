package dev.kyrion.core.automation

import dev.kyrion.core.action.ActionOrchestrator
import dev.kyrion.core.capability.*
import dev.kyrion.core.gateway.GatewayNode
import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.IntegrationConnectionRepository
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import org.springframework.core.task.TaskExecutor
import java.util.UUID

class ZigbeeButtonBindingTest {
    private val owner = UUID.randomUUID()
    private val button = UUID.randomUUID()
    private val target = UUID.randomUUID()
    private val repository = mock(ZigbeeButtonBindingRepository::class.java)
    private val connections = mock(IntegrationConnectionRepository::class.java)
    private val catalog = mock(DeviceCatalogService::class.java)
    private val orchestrator = mock(ActionOrchestrator::class.java)
    private val tasks = mutableListOf<Runnable>()
    private val service = ZigbeeButtonBindingService(repository, connections, catalog, orchestrator,
        TaskExecutor { tasks.add(it) })
    private val binding = ZigbeeButtonBinding("single", targetDeviceId = target, action = "turn_on")
    private val node = mock(GatewayNode::class.java)

    private fun queue() {
        `when`(node.ownerId).thenReturn(owner)
        val connection = mock(IntegrationConnection::class.java)
        `when`(connection.id).thenReturn(button)
        `when`(connection.provider).thenReturn("zigbee")
        `when`(connection.endpointHost).thenReturn("0x0011223344556677")
        `when`(connections.findAll(owner)).thenReturn(listOf(connection))
        `when`(catalog.devices(owner)).thenReturn(listOf(
            DeviceCatalogItem(button, "zigbee", "switch", "Button", "Button", null,
                listOf(DeviceCapabilityView("button.events")), DeviceAvailability.ONLINE, null, null),
            DeviceCatalogItem(target, "zigbee", "light", "Lamp", "Lamp", null,
                listOf(DeviceCapabilityView(DeviceCommandService.POWER_SET)), DeviceAvailability.ONLINE, null, null)
        ))
        `when`(repository.find(owner, button)).thenReturn(listOf(binding))
        service.handle(node, "0x0011223344556677", "single")
        assertEquals(1, tasks.size)
        verifyNoInteractions(orchestrator)
    }

    @Test fun `deleted binding prevents queued action execution`() {
        queue()
        `when`(repository.find(owner, button)).thenReturn(emptyList())
        tasks.single().run()
        verifyNoInteractions(orchestrator)
    }

    @Test fun `reconfigured binding cannot execute its previously captured target or action`() {
        queue()
        `when`(repository.find(owner, button)).thenReturn(listOf(binding.copy(targetDeviceId = UUID.randomUUID())))
        tasks.single().run()
        verifyNoInteractions(orchestrator)
    }

    @Test fun `unchanged binding executes through the action orchestrator once`() {
        queue()
        tasks.single().run()
        assertEquals(1, mockingDetails(orchestrator).invocations.count { it.method.name == "execute" })
    }
}

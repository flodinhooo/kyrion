package dev.kyrion.core.integration

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.capability.*
import dev.kyrion.core.home.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import java.time.Instant
import java.util.UUID

class HomeAssistantImportTest {
    private val mapper = jacksonObjectMapper().findAndRegisterModules()
    private val client = HomeAssistantClient(HomeAssistantConfiguration("", "", ""), mapper)
    private val id = "a".repeat(32)
    private fun row(state: String = "21.5", area: String? = null) = mapOf(
        "id" to id, "entity" to "sensor.temperature", "name" to "Sensor", "area" to area,
        "state" to state, "class" to "temperature", "unit" to "°C", "updated" to "2026-09-06T10:00:00Z"
    )

    @Test
    fun `room mapping uses only unique normalized existing names`() {
        val room = Room(UUID.randomUUID(), " Wohnzimmer ", Instant.now(), Instant.now())
        assertNull(importedRoom(null, listOf(room)))
        assertNull(importedRoom("Kitchen", listOf(room)))
        assertNull(importedRoom("Wohnzimmer OG", listOf(room)))
        assertEquals(room.id, importedRoom(" wOhNzImMeR ", listOf(room)))
        assertNull(importedRoom("Wohnzimmer", listOf(room, room.copy(id = UUID.randomUUID()))))
    }

    @Test
    fun `read only states and sensor values are bounded and offline is explicit`() {
        val device = client.parse(mapper.valueToTree(listOf(row()))).single()
        assertEquals(21.5, device.state.temperatureCelsius)
        assertEquals(listOf("temperature.read"), device.capabilities)
        assertEquals(DeviceAvailability.ONLINE, device.availability)
        val offline = client.parse(mapper.valueToTree(listOf(row("unavailable")))).single()
        assertEquals(DeviceAvailability.OFFLINE, offline.availability)
        assertNull(offline.state.temperatureCelsius)
        assertEquals(
            DeviceAvailability.DEGRADED,
            client.parse(mapper.valueToTree(listOf(row("NaN")))).single().availability
        )
        assertThrows(HomeAssistantException::class.java) { client.parse(mapper.valueToTree(listOf(row() - "id"))) }
        assertThrows(HomeAssistantException::class.java) { client.parse(mapper.readTree("{}")) }
        assertThrows(HomeAssistantException::class.java) { client.parse(mapper.valueToTree(listOf(row(), row()))) }
    }

    @Test
    fun `reimport preserves Kyrion identity and updates name room state and availability`() {
        val owner = UUID.randomUUID()
        val connectionId = UUID.randomUUID()
        val room = Room(UUID.randomUUID(), "Wohnzimmer", Instant.now(), Instant.now())
        val existing = IntegrationConnection(
            connectionId, owner, HOME_ASSISTANT_PROVIDER, "Old", id,
            byteArrayOf(), byteArrayOf(), 1, Instant.now(), Instant.now()
        )
        val connections = mock(IntegrationConnectionRepository::class.java)
        val rooms = mock(RoomRepository::class.java)
        val observations = mock(DeviceObservationRepository::class.java)
        val readings = mock(ImportedDeviceRepository::class.java)
        `when`(connections.findAll(owner)).thenReturn(listOf(existing))
        `when`(rooms.all(owner)).thenReturn(listOf(room))
        `when`(rooms.assignConnection(owner, connectionId, room.id)).thenReturn(true)
        `when`(rooms.assignConnection(owner, connectionId, null)).thenReturn(true)
        val reconciler = HomeAssistantReconciler(connections, rooms, observations, readings)
        val device = client.parse(mapper.valueToTree(listOf(row("25", "wohnzimmer"))))
        reconciler.reconcile(owner, device)
        reconciler.reconcile(owner, client.parse(mapper.valueToTree(listOf(row("unavailable")))))
        assertTrue(mockingDetails(connections).invocations.none { it.method.name == "save" })
        verify(rooms).assignConnection(owner, connectionId, room.id)
        verify(rooms).assignConnection(owner, connectionId, null)
        verify(readings).save(
            owner,
            ImportedDeviceState(connectionId, "Home Assistant", device.single().state, listOf("temperature.read"))
        )
        assertEquals("", existing.view().endpointHost)
    }

    @Test
    fun `configuration is owner scoped and rejects unsafe destinations`() {
        val owner = UUID.randomUUID()
        val config = HomeAssistantConfiguration("http://192.168.1.10:8123", "test-token", owner.toString())
        assertTrue(config.configured(owner))
        assertFalse(config.configured(UUID.randomUUID()))
        assertEquals("/api/template", config.request(owner, "{}").uri().path)
        assertThrows(HomeAssistantException::class.java) { config.request(UUID.randomUUID(), "{}") }
        for (url in listOf("http://8.8.8.8", "http://user@192.168.1.10", "http://192.168.1.10/other")) {
            assertThrows(HomeAssistantException::class.java) {
                HomeAssistantConfiguration(
                    url,
                    "token",
                    owner.toString()
                ).request(owner, "{}")
            }
        }
    }
}

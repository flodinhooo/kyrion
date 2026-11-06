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
    fun `light and contact mappings remain read only and unavailable values are never invented`() {
        val lamp = row("on") + mapOf("entity" to "light.hue", "class" to null, "brightness" to 128, "hue" to 215.0, "saturation" to 80.0)
        val light = client.parse(mapper.valueToTree(listOf(lamp))).single()
        assertEquals(true, light.state.on)
        assertEquals(50, light.state.brightness)
        assertEquals(215.0, light.state.hue)
        assertNull(light.state.battery)
        assertEquals(listOf("power.read"), light.capabilities)
        val unavailable = client.parse(mapper.valueToTree(listOf(lamp + mapOf("state" to "unavailable")))).single()
        assertEquals(DeviceAvailability.OFFLINE, unavailable.availability)
        assertNull(unavailable.state.on)
        assertNull(unavailable.state.brightness)
        val contact = client.parse(mapper.valueToTree(listOf(row("on") + mapOf("entity" to "binary_sensor.door", "class" to "door")))).single()
        assertEquals(listOf("contact.read"), contact.capabilities)
        assertEquals(true, contact.state.on)
    }

    @Test
    fun `unknown missing and mixed sensor data remain semantically distinct`() {
        val unknown = client.parse(mapper.valueToTree(listOf(row("unknown")))).single()
        assertEquals(DeviceAvailability.UNKNOWN, unknown.availability)
        assertNull(unknown.state.temperatureCelsius)
        val mixed = client.parse(mapper.valueToTree(listOf(row(), row("unavailable") + mapOf("entity" to "sensor.battery", "class" to "battery", "unit" to "%")))).single()
        assertEquals(DeviceAvailability.DEGRADED, mixed.availability)
        assertEquals(21.5, mixed.state.temperatureCelsius)
        assertNull(mixed.state.battery)
        val fahrenheit = client.parse(mapper.valueToTree(listOf(row("68") + mapOf("unit" to "\u00b0F")))).single()
        assertEquals(20.0, fahrenheit.state.temperatureCelsius)
        assertEquals(Instant.parse("2026-09-06T10:00:00Z"), fahrenheit.state.measuredAt)
    }

    @Test
    fun `credential connection is not reconciled as a missing physical device`() {
        val owner = UUID.randomUUID()
        val config = IntegrationConnection(UUID.randomUUID(), owner, HOME_ASSISTANT_PROVIDER, "Home Assistant", "192.168.1.5", byteArrayOf(1), byteArrayOf(2), 1, Instant.now(), Instant.now())
        val connections = mock(IntegrationConnectionRepository::class.java)
        val rooms = mock(RoomRepository::class.java)
        val observations = mock(DeviceObservationRepository::class.java)
        `when`(connections.findAll(owner)).thenReturn(listOf(config))
        `when`(rooms.all(owner)).thenReturn(emptyList())
        HomeAssistantReconciler(connections, rooms, observations, mock(ImportedDeviceRepository::class.java)).reconcile(owner, emptyList())
        verifyNoInteractions(observations)
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

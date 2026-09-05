package dev.kyrion.core.capability

import dev.kyrion.core.home.Room
import dev.kyrion.core.home.RoomRepository
import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.IntegrationConnectionRepository
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test
import java.time.Instant
import java.time.Clock
import java.time.ZoneOffset
import java.util.UUID

class DeviceCatalogServiceTest {
    @Test
    fun `catalog exposes only owner metadata rooms and stable capabilities`() {
        val owner = UUID.randomUUID()
        val otherOwner = UUID.randomUUID()
        val room = Room(UUID.randomUUID(), "Schlafzimmer", Instant.now(), Instant.now())
        val connections = CatalogConnections(
            listOf(
                connection(owner, "Bedroom panels", room.id),
                connection(owner, "Unassigned panels", null),
                connection(otherOwner, "Private panels", room.id),
            ),
        )
        val catalog = DeviceCatalogService(connections, CatalogRooms(owner, room), EmptyObservations())

        val devices = catalog.devices(owner)

        assertEquals(listOf("Bedroom panels", "Unassigned panels"), devices.map { it.displayName })
        assertEquals("Schlafzimmer", devices.first().room?.name)
        assertNull(devices.last().room)
        assertEquals(DeviceCatalogService.NANOLEAF_CAPABILITIES, devices.first().capabilities.map { it.id })
        assertEquals(DeviceAvailability.UNKNOWN, devices.first().availability)
        assertNull(devices.first().observedAt)
    }

    @Test
    fun `catalog expires availability without discarding the last observation time`() {
        val owner = UUID.randomUUID()
        val room = Room(UUID.randomUUID(), "Studio", Instant.now(), Instant.now())
        val device = connection(owner, "Panels", room.id)
        val now = Instant.parse("2026-08-05T12:00:00Z")
        val fresh = DeviceObservation(device.id, owner, DeviceAvailability.ONLINE, now.minusSeconds(30))
        val stale = fresh.copy(observedAt = now.minusSeconds(61))

        val freshCatalog = DeviceCatalogService(
            CatalogConnections(listOf(device)), CatalogRooms(owner, room), CatalogObservations(listOf(fresh)),
            Clock.fixed(now, ZoneOffset.UTC),
        ).devices(owner).single()
        val staleCatalog = DeviceCatalogService(
            CatalogConnections(listOf(device)), CatalogRooms(owner, room), CatalogObservations(listOf(stale)),
            Clock.fixed(now, ZoneOffset.UTC),
        ).devices(owner).single()

        assertEquals(DeviceAvailability.ONLINE, freshCatalog.availability)
        assertEquals(DeviceAvailability.UNKNOWN, staleCatalog.availability)
        assertEquals(stale.observedAt, staleCatalog.observedAt)
    }

    @Test
    fun `shelly retains timestamped measurements after availability expires`() {
        val owner = UUID.randomUUID()
        val now = Instant.parse("2026-09-05T12:00:00Z")
        val measuredAt = now.minusSeconds(7200)
        val sensor = connection(owner, "Bedroom sensor", null).copy(provider = "shelly",
            deviceClass = dev.kyrion.core.integration.DeviceClass.SENSOR)
        val readings = object : dev.kyrion.core.integration.ShellySensorRepository {
            override fun all(ownerId: UUID) = if (ownerId == owner) listOf(
                dev.kyrion.core.integration.StoredShellyReading(sensor.id, owner,
                    dev.kyrion.core.integration.ShellySensorReading(21.5, 49.0, 80.0), measuredAt),
            ) else emptyList()
            override fun save(value: dev.kyrion.core.integration.StoredShellyReading) = error("unused")
        }
        val catalog = DeviceCatalogService(CatalogConnections(listOf(sensor)),
            CatalogRooms(owner, Room(UUID.randomUUID(), "Bedroom", now, now)),
            CatalogObservations(listOf(DeviceObservation(sensor.id, owner, DeviceAvailability.ONLINE, measuredAt))),
            Clock.fixed(now, ZoneOffset.UTC), shellyReadings = readings)
        val item = catalog.devices(owner).single()
        assertEquals(DeviceAvailability.UNKNOWN, item.availability)
        assertEquals(21.5, item.state?.temperatureCelsius)
        assertEquals(49.0, item.state?.relativeHumidity)
        assertEquals(measuredAt, item.state?.measuredAt)
        assertEquals(listOf("temperature.read", "humidity.read", "battery.read"), item.capabilities.map { it.id })
        assertEquals(emptyList<DeviceCatalogItem>(), catalog.devices(UUID.randomUUID()))
    }

    private fun connection(ownerId: UUID, name: String, roomId: UUID?) = IntegrationConnection(
        UUID.randomUUID(), ownerId, "nanoleaf", name, "192.168.1.10",
        byteArrayOf(1), byteArrayOf(2), 1, Instant.now(), Instant.now(), roomId,
    )
}

private class EmptyObservations : DeviceObservationRepository {
    override fun findAll(ownerId: UUID) = emptyList<DeviceObservation>()
    override fun save(observation: DeviceObservation) = observation
}

private class CatalogObservations(private val values: List<DeviceObservation>) : DeviceObservationRepository {
    override fun findAll(ownerId: UUID) = values.filter { it.ownerId == ownerId }
    override fun save(observation: DeviceObservation) = observation
}

private class CatalogConnections(private val values: List<IntegrationConnection>) : IntegrationConnectionRepository {
    override fun findAll(ownerId: UUID) = values.filter { it.ownerId == ownerId }
    override fun find(ownerId: UUID, id: UUID) = values.find { it.ownerId == ownerId && it.id == id }
    override fun save(connection: IntegrationConnection) = error("not used")
    override fun rename(ownerId: UUID, id: UUID, displayName: String, updatedAt: Instant) = error("not used")
    override fun delete(ownerId: UUID, id: UUID) = false
}

private class CatalogRooms(private val owner: UUID, private val room: Room) : RoomRepository {
    override fun all(ownerId: UUID) = if (ownerId == owner) listOf(room) else emptyList()
    override fun find(ownerId: UUID, id: UUID) = all(ownerId).find { it.id == id }
    override fun create(ownerId: UUID, room: Room) = error("not used")
    override fun rename(ownerId: UUID, id: UUID, name: String, updatedAt: Instant) = error("not used")
    override fun delete(ownerId: UUID, id: UUID) = false
    override fun assignConnection(ownerId: UUID, connectionId: UUID, roomId: UUID?) = false
}

package dev.kyrion.core.capability

import dev.kyrion.core.activity.ActivityEvent
import dev.kyrion.core.activity.ActivityEventRepository
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.home.Room
import dev.kyrion.core.home.RoomRepository
import dev.kyrion.core.integration.CredentialCipher
import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.integration.NanoleafDeviceState
import dev.kyrion.core.integration.NanoleafGateway
import dev.kyrion.core.integration.NanoleafIntegrationService
import dev.kyrion.core.integration.NanoleafScenes
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Path
import java.time.Instant
import java.util.UUID

class DeviceCommandServiceTest {
    @TempDir lateinit var temp: Path

    @Test
    fun `brightness command resolves every owner Nanoleaf in the requested room`() {
        val owner = UUID.randomUUID()
        val bedroom = Room(UUID.randomUUID(), "Schlafzimmer", Instant.now(), Instant.now())
        val rooms = FakeRooms(owner, bedroom)
        val connections = FakeConnections()
        val events = mutableListOf<ActivityEvent>()
        val activity = ActivityService(FakeActivityRepository(events))
        val gateway = FakeGateway()
        val observations = CommandObservations()
        val nanoleaf = NanoleafIntegrationService(
            connections,
            gateway,
            CredentialCipher(temp.resolve("credential.key").toString()),
            activity,
        )
        val first = nanoleaf.pair(owner, "192.168.1.41", "Bett").id
        val second = nanoleaf.pair(owner, "192.168.1.42", "Wand").id
        connections.assign(owner, first, bedroom.id)
        connections.assign(owner, second, bedroom.id)
        val commands = DeviceCommandService(rooms, connections, nanoleaf, activity, observations)

        val result = commands.execute(
            owner,
            ExecuteDeviceCommandRequest(
                DeviceCommandService.BRIGHTNESS_SET,
                DeviceTargetSelector("schlafzimmer", "nanoleaf"),
                DeviceCommandArguments(brightness = 20),
            ),
        )

        assertEquals(2, result.requested)
        assertEquals(2, result.succeeded)
        assertEquals(listOf(20, 20), gateway.brightnessValues)
        assertEquals(2, observations.values.count { it.availability == DeviceAvailability.ONLINE })
        val commandEvents = events.filter { it.correlationId == result.correlationId }
        assertTrue(commandEvents.any { it.status == ActivityStatus.PROPOSED && it.source == "velora" })
        assertEquals(2, commandEvents.count { it.status == ActivityStatus.SUCCEEDED })
    }

    @Test
    fun `command never crosses owner or room boundaries`() {
        val owner = UUID.randomUUID()
        val otherOwner = UUID.randomUUID()
        val bedroom = Room(UUID.randomUUID(), "Schlafzimmer", Instant.now(), Instant.now())
        val connections = FakeConnections()
        val activity = ActivityService(FakeActivityRepository(mutableListOf()))
        val nanoleaf = NanoleafIntegrationService(
            connections,
            FakeGateway(),
            CredentialCipher(temp.resolve("credential.key").toString()),
            activity,
        )
        val otherDevice = nanoleaf.pair(otherOwner, "192.168.1.50", "Other").id
        connections.assign(otherOwner, otherDevice, bedroom.id)
        val commands = DeviceCommandService(
            FakeRooms(owner, bedroom), connections, nanoleaf, activity, CommandObservations(),
        )

        assertThrows(DeviceTargetNotFoundException::class.java) {
            commands.execute(
                owner,
                ExecuteDeviceCommandRequest(
                    DeviceCommandService.POWER_SET,
                    DeviceTargetSelector("Schlafzimmer", "nanoleaf"),
                    DeviceCommandArguments(on = true),
                ),
            )
        }
    }

    @Test
    fun `stable device id targets exactly one owner device`() {
        val owner = UUID.randomUUID()
        val room = Room(UUID.randomUUID(), "Schlafzimmer", Instant.now(), Instant.now())
        val connections = FakeConnections()
        val activity = ActivityService(FakeActivityRepository(mutableListOf()))
        val gateway = FakeGateway()
        val nanoleaf = NanoleafIntegrationService(
            connections, gateway, CredentialCipher(temp.resolve("credential.key").toString()), activity,
        )
        val selected = nanoleaf.pair(owner, "192.168.1.60", "Bett").id
        nanoleaf.pair(owner, "192.168.1.61", "Wand")
        connections.assign(owner, selected, room.id)
        val commands = DeviceCommandService(
            FakeRooms(owner, room), connections, nanoleaf, activity, CommandObservations(),
        )

        val result = commands.execute(
            owner,
            ExecuteDeviceCommandRequest(
                DeviceCommandService.POWER_SET,
                DeviceTargetSelector(provider = "nanoleaf", deviceId = selected),
                DeviceCommandArguments(on = true),
            ),
        )

        assertEquals(1, result.requested)
        assertEquals("Bett", result.outcomes.single().displayName)
    }
}

private class CommandObservations : DeviceObservationRepository {
    val values = mutableListOf<DeviceObservation>()
    override fun findAll(ownerId: UUID) = values.filter { it.ownerId == ownerId }
    override fun save(observation: DeviceObservation) = observation.also(values::add)
}

private class FakeActivityRepository(private val events: MutableList<ActivityEvent>) : ActivityEventRepository {
    override fun append(event: ActivityEvent) = event.also(events::add)
    override fun findRecent(limit: Int) = events.takeLast(limit).reversed()
}

private class FakeRooms(private val owner: UUID, private val room: Room) : RoomRepository {
    override fun all(ownerId: UUID) = if (ownerId == owner) listOf(room) else emptyList()
    override fun find(ownerId: UUID, id: UUID) = all(ownerId).singleOrNull { it.id == id }
    override fun create(ownerId: UUID, room: Room) = error("not used")
    override fun rename(ownerId: UUID, id: UUID, name: String, updatedAt: Instant) = error("not used")
    override fun delete(ownerId: UUID, id: UUID) = false
    override fun assignConnection(ownerId: UUID, connectionId: UUID, roomId: UUID?) = false
}

private class FakeConnections : IntegrationConnectionRepository {
    private val values = mutableListOf<IntegrationConnection>()
    override fun findAll(ownerId: UUID) = values.filter { it.ownerId == ownerId }
    override fun find(ownerId: UUID, id: UUID) = values.find { it.ownerId == ownerId && it.id == id }
    override fun save(connection: IntegrationConnection) = connection.also(values::add)
    override fun rename(ownerId: UUID, id: UUID, displayName: String, updatedAt: Instant): IntegrationConnection? = null
    override fun delete(ownerId: UUID, id: UUID) = values.removeIf { it.ownerId == ownerId && it.id == id }
    fun assign(ownerId: UUID, id: UUID, roomId: UUID) {
        val index = values.indexOfFirst { it.ownerId == ownerId && it.id == id }
        values[index] = values[index].copy(roomId = roomId)
    }
}

private class FakeGateway : NanoleafGateway {
    val brightnessValues = mutableListOf<Int>()
    override fun pair(host: String) = "token-$host"
    override fun state(host: String, token: String) = NanoleafDeviceState("Panels", "NL", host, true, 20)
    override fun setPower(host: String, token: String, on: Boolean) = Unit
    override fun setBrightness(host: String, token: String, brightness: Int) { brightnessValues += brightness }
    override fun scenes(host: String, token: String) = NanoleafScenes(null, emptyList())
    override fun selectScene(host: String, token: String, name: String) = Unit
    override fun setColor(host: String, token: String, hue: Int, saturation: Int) = Unit
    override fun setColorTemperature(host: String, token: String, kelvin: Int) = Unit
}

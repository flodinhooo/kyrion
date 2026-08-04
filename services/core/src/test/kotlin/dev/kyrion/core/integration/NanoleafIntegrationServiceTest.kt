package dev.kyrion.core.integration

import dev.kyrion.core.activity.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Path
import java.util.UUID

class NanoleafIntegrationServiceTest {
    @TempDir lateinit var temp: Path

    @Test
    fun `connections and commands remain owner scoped and credentials remain protected`() {
        val connections = InMemoryConnections()
        val gateway = FakeNanoleafGateway()
        val activityEvents = mutableListOf<ActivityEvent>()
        val activity = ActivityService(object : ActivityEventRepository {
            override fun append(event: ActivityEvent) = event.also(activityEvents::add)
            override fun findRecent(limit: Int) = activityEvents.takeLast(limit).reversed()
        })
        val service = NanoleafIntegrationService(
            connections, gateway, CredentialCipher(temp.resolve("credential.key").toString()), activity,
        )
        val alice = UUID.randomUUID()
        val bob = UUID.randomUUID()

        val aliceConnection = service.pair(alice, "192.168.1.42", "Living room")
        service.pair(bob, "192.168.1.42", "Studio")

        assertEquals(listOf("Living room"), service.connections(alice).map { it.displayName })
        assertEquals(listOf("Studio"), service.connections(bob).map { it.displayName })
        assertThrows(IntegrationNotFoundException::class.java) { service.state(bob, aliceConnection.id) }
        assertThrows(IntegrationConfirmationRequiredException::class.java) { service.power(alice, aliceConnection.id, true, false) }

        val state = service.power(alice, aliceConnection.id, true, true)
        assertTrue(state.on)
        val stored = connections.find(alice, aliceConnection.id)!!
        assertFalse(String(stored.credentialCiphertext).contains("token-192.168.1.42"))
        assertTrue(activityEvents.any { it.category == ActivityCategory.INTEGRATION && it.actorId == alice.toString() })
    }

    @Test
    fun `pairing rejects public addresses before network access`() {
        val gateway = FakeNanoleafGateway()
        val service = NanoleafIntegrationService(
            InMemoryConnections(), gateway, CredentialCipher(temp.resolve("credential.key").toString()),
            ActivityService(object : ActivityEventRepository {
                override fun append(event: ActivityEvent) = event
                override fun findRecent(limit: Int) = emptyList<ActivityEvent>()
            }),
        )
        assertThrows(IntegrationInvalidHostException::class.java) { service.pair(UUID.randomUUID(), "8.8.8.8", null) }
        assertEquals(0, gateway.pairCalls)
    }
}

private class InMemoryConnections : IntegrationConnectionRepository {
    private val values = mutableListOf<IntegrationConnection>()
    override fun findAll(ownerId: UUID) = values.filter { it.ownerId == ownerId }
    override fun find(ownerId: UUID, id: UUID) = values.find { it.ownerId == ownerId && it.id == id }
    override fun save(connection: IntegrationConnection) = connection.also(values::add)
    override fun rename(ownerId: UUID, id: UUID, displayName: String, updatedAt: java.time.Instant): IntegrationConnection? {
        val index = values.indexOfFirst { it.ownerId == ownerId && it.id == id }; if (index < 0) return null
        return values[index].copy(displayName = displayName, updatedAt = updatedAt).also { values[index] = it }
    }
    override fun delete(ownerId: UUID, id: UUID) = values.removeIf { it.ownerId == ownerId && it.id == id }
}

private class FakeNanoleafGateway : NanoleafGateway {
    var pairCalls = 0
    private var on = false
    override fun pair(host: String) = "token-$host".also { pairCalls++ }
    override fun state(host: String, token: String) = NanoleafDeviceState("Test panels", "NL42", "serial", on, 55)
    override fun setPower(host: String, token: String, on: Boolean) { this.on = on }
    override fun setBrightness(host: String, token: String, brightness: Int) = Unit
    override fun scenes(host: String, token: String) = NanoleafScenes("Forest", listOf("Forest", "Northern Lights"))
    override fun selectScene(host: String, token: String, name: String) = Unit
}

package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.ObjectMapper
import dev.kyrion.core.activity.*
import dev.kyrion.core.capability.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID

class ShellyIntegrationTest {
    private val mapper = ObjectMapper()

    @Test
    fun `parses sensor values including zero without coercing invalid provider data`() {
        val reading = ShellyResponses.reading(mapper.readTree("""{"temperature:0":{"tC":0},"humidity:0":{"rh":48.5},"devicepower:0":{"battery":{"percent":0}}}"""))
        assertEquals(ShellySensorReading(0.0, 48.5, 0.0), reading)
        assertEquals(ShellySensorReading(null, null, null), ShellyResponses.reading(mapper.readTree("""{"temperature:0":{"tC":null},"humidity:0":{"rh":null}}""")))
        for (body in listOf("{}", """{"temperature:0":{"tC":"20"},"humidity:0":{"rh":40}}""", """{"temperature:0":{"tC":20},"humidity:0":{"rh":101}}""")) {
            assertEquals("SHELLY_INVALID_RESPONSE", assertThrows(ShellyException::class.java) { ShellyResponses.reading(mapper.readTree(body)) }.code)
        }
    }

    @Test
    fun `only supported HT generations are accepted and protected devices fail explicitly`() {
        ShellyResponses.validateDevice(mapper.readTree("""{"gen":3,"app":"HT","auth_en":false}"""))
        ShellyResponses.validateDevice(mapper.readTree("""{"gen":2,"app":"HT","auth_en":false}"""))
        assertEquals("SHELLY_UNSUPPORTED_DEVICE", assertThrows(ShellyException::class.java) {
            ShellyResponses.validateDevice(mapper.readTree("""{"gen":3,"app":"PlugS"}"""))
        }.code)
        assertEquals("SHELLY_AUTH_REQUIRED", assertThrows(ShellyException::class.java) {
            ShellyResponses.validateDevice(mapper.readTree("""{"gen":3,"app":"HT","auth_en":true}"""))
        }.code)
    }

    @Test
    fun `private addresses only without DNS URLs loopback or link local metadata`() {
        for (host in listOf("8.8.8.8", "127.0.0.1", "169.254.169.254", "localhost", "192.168.1.256", "http://192.168.1.2", "192.168.1.2:80", "::1")) {
            assertThrows(IntegrationInvalidHostException::class.java) { privateNetworkIpv4(host) }
        }
        assertEquals("192.168.1.2", privateNetworkIpv4("192.168.001.002"))
        assertEquals("10.0.0.2", privateNetworkIpv4("10.0.0.2"))
    }

    @Test
    fun `connection requires confirmation persists readings and remains owner scoped during sleep`() {
        var saved: IntegrationConnection? = null
        var saves = 0
        val connections = object : IntegrationConnectionRepository {
            override fun findAll(ownerId: UUID) = listOfNotNull(saved).filter { it.ownerId == ownerId }
            override fun find(ownerId: UUID, id: UUID) = saved?.takeIf { it.ownerId == ownerId && it.id == id }
            override fun save(connection: IntegrationConnection) = connection.also { saved = it; saves++ }
            override fun rename(ownerId: UUID, id: UUID, displayName: String, updatedAt: Instant) = error("unused")
            override fun delete(ownerId: UUID, id: UUID) = false
        }
        val readings = mock(ShellySensorRepository::class.java)
        val observations = mock(DeviceObservationRepository::class.java)
        val owner = UUID.randomUUID()
        val events = mutableListOf<ActivityEvent>()
        val activity = ActivityService(object : ActivityEventRepository {
            override fun append(event: ActivityEvent) = event.also(events::add)
            override fun findRecent(limit: Int) = events.takeLast(limit)
        })
        val now = Instant.parse("2026-09-05T10:00:00Z")
        var sleeping = false
        var calls = 0
        val gateway = object : ShellyGateway {
            override fun read(host: String): ShellySensorReading {
                calls++
                if (sleeping) throw ShellyException("SHELLY_UNAVAILABLE")
                return ShellySensorReading(21.5, 47.0, 95.0)
            }
        }
        val service = ShellyIntegrationService(connections, readings, observations, gateway, activity, Clock.fixed(now, ZoneOffset.UTC))
        assertThrows(IntegrationConfirmationRequiredException::class.java) { service.connect(owner, "192.168.1.2", null, false) }
        assertThrows(IntegrationInvalidHostException::class.java) { service.connect(owner, "8.8.8.8", null, true) }
        assertEquals(0, calls)
        val view = service.connect(owner, "192.168.1.2", "Bedroom", true)
        assertEquals("sensor", view.deviceClass)
        assertEquals(view.id, service.connect(owner, "192.168.1.2", null, true).id)
        assertEquals(1, saves)
        verify(readings, times(2)).save(StoredShellyReading(view.id, owner, ShellySensorReading(21.5, 47.0, 95.0), now))
        assertTrue(events.all { it.actorId == owner.toString() })
        sleeping = true
        assertEquals(DeviceAvailability.UNKNOWN, service.observe(owner, saved!!))
        verifyNoMoreInteractions(readings)
        assertThrows(IntegrationNotFoundException::class.java) { service.observe(UUID.randomUUID(), saved!!) }
        assertEquals(3, calls)
    }
}

package dev.kyrion.core.capability

import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.IntegrationConnectionRepository
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import org.mockito.Mockito.mock
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID

class DeviceObservationServiceTest {
    @Test
    fun `refresh delegates every supported connection to its provider observer`() {
        val owner = UUID.randomUUID()
        val now = Instant.parse("2026-08-19T15:00:00Z")
        val nanoleaf = connection(owner, "nanoleaf", "192.168.1.20")
        val zigbee = connection(owner, "zigbee", "0x00124b")
        val future = connection(owner, "future-provider", "local-device")
        val saved = mutableListOf<DeviceObservation>()
        val service = DeviceObservationService(
            ObservationConnections(listOf(nanoleaf, zigbee, future)),
            RecordingObservations(saved),
            listOf(
                FixedProviderObserver("nanoleaf", DeviceAvailability.ONLINE),
                FixedProviderObserver("zigbee", DeviceAvailability.DEGRADED),
            ),
            mock(ActivityService::class.java),
            Clock.fixed(now, ZoneOffset.UTC),
        )

        val result = service.refresh(owner)

        assertEquals(listOf(nanoleaf.id, zigbee.id), result.map { it.connectionId })
        assertEquals(listOf(DeviceAvailability.ONLINE, DeviceAvailability.DEGRADED), saved.map { it.availability })
        assertEquals(listOf(now, now), saved.map { it.observedAt })
    }

    private fun connection(owner: UUID, provider: String, endpoint: String) = IntegrationConnection(
        UUID.randomUUID(), owner, provider, provider, endpoint, byteArrayOf(1), byteArrayOf(2), 1, Instant.now(), Instant.now(), null,
    )
}

private class FixedProviderObserver(
    override val provider: String,
    private val availability: DeviceAvailability,
) : DeviceProviderObserver {
    override fun observe(ownerId: UUID, connection: IntegrationConnection) = availability
}

private class ObservationConnections(private val values: List<IntegrationConnection>) : IntegrationConnectionRepository {
    override fun findAll(ownerId: UUID) = values.filter { it.ownerId == ownerId }
    override fun find(ownerId: UUID, id: UUID) = values.find { it.ownerId == ownerId && it.id == id }
    override fun save(connection: IntegrationConnection) = error("not used")
    override fun rename(ownerId: UUID, id: UUID, displayName: String, updatedAt: Instant) = error("not used")
    override fun delete(ownerId: UUID, id: UUID) = false
}

private class RecordingObservations(private val values: MutableList<DeviceObservation>) : DeviceObservationRepository {
    override fun findAll(ownerId: UUID) = values.filter { it.ownerId == ownerId }
    override fun save(observation: DeviceObservation) = observation.also(values::add)
}

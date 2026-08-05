package dev.kyrion.core.capability

import com.fasterxml.jackson.annotation.JsonValue
import dev.kyrion.core.home.RoomRepository
import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.integration.NanoleafIntegrationService
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController
import java.util.UUID
import java.time.Instant
import java.time.Clock
import java.time.Duration

data class DeviceCapabilityView(val id: String)

data class DeviceRoomView(val id: UUID, val name: String)

enum class DeviceAvailability(@get:JsonValue val value: String) {
    ONLINE("online"),
    OFFLINE("offline"),
    DEGRADED("degraded"),
    UNKNOWN("unknown"),
}

data class DeviceCatalogItem(
    val id: UUID,
    val provider: String,
    val displayName: String,
    val room: DeviceRoomView?,
    val capabilities: List<DeviceCapabilityView>,
    val availability: DeviceAvailability,
    val observedAt: Instant?,
)

@Service
class DeviceCatalogService(
    private val connections: IntegrationConnectionRepository,
    private val rooms: RoomRepository,
    private val observations: DeviceObservationRepository,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun devices(ownerId: UUID): List<DeviceCatalogItem> {
        val ownerRooms = rooms.all(ownerId).associateBy { it.id }
        val ownerObservations = observations.findAll(ownerId).associateBy { it.connectionId }
        return connections.findAll(ownerId).map { connection ->
            val observation = ownerObservations[connection.id]
            val currentAvailability = observation?.takeIf { isFresh(it.observedAt) }?.availability
                ?: DeviceAvailability.UNKNOWN
            DeviceCatalogItem(
                id = connection.id,
                provider = connection.provider,
                displayName = connection.displayName,
                room = connection.roomId?.let(ownerRooms::get)?.let { DeviceRoomView(it.id, it.name) },
                capabilities = capabilities(connection),
                availability = currentAvailability,
                observedAt = observation?.observedAt,
            )
        }
    }

    private fun isFresh(observedAt: Instant): Boolean {
        val now = clock.instant()
        return !observedAt.isAfter(now) && Duration.between(observedAt, now) <= OBSERVATION_TTL
    }

    private fun capabilities(connection: IntegrationConnection): List<DeviceCapabilityView> = when (connection.provider) {
        NanoleafIntegrationService.PROVIDER -> NANOLEAF_CAPABILITIES.map(::DeviceCapabilityView)
        else -> emptyList()
    }

    companion object {
        val OBSERVATION_TTL: Duration = Duration.ofSeconds(60)
        val NANOLEAF_CAPABILITIES = listOf(
            DeviceCommandService.POWER_SET,
            DeviceCommandService.BRIGHTNESS_SET,
            "light.setColour",
            "light.setColourTemperature",
            "light.activateScene",
        )
    }
}

@RestController
@RequestMapping("/v1/devices")
class DeviceCatalogController(
    private val catalog: DeviceCatalogService,
    private val observations: DeviceObservationService,
) {
    @GetMapping
    fun devices(request: HttpServletRequest) = catalog.devices(request.ownerId())

    @PostMapping("/observations/refresh")
    fun refresh(request: HttpServletRequest): List<DeviceCatalogItem> {
        val ownerId = request.ownerId()
        observations.refresh(ownerId)
        return catalog.devices(ownerId)
    }

    private fun HttpServletRequest.ownerId() =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw DeviceCommandUnauthenticatedException()
}

package dev.kyrion.core.capability

import com.fasterxml.jackson.annotation.JsonValue
import dev.kyrion.core.home.RoomRepository
import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.integration.NanoleafIntegrationService
import dev.kyrion.core.gateway.ZigbeeDeviceSyncService
import dev.kyrion.core.gateway.GatewayService
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
data class DeviceStateView(
    val on: Boolean?,
    val brightness: Int?,
    val hue: Double?,
    val saturation: Double?,
    val colorTemperature: Int?,
)

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
    val hardwareName: String,
    val room: DeviceRoomView?,
    val capabilities: List<DeviceCapabilityView>,
    val availability: DeviceAvailability,
    val observedAt: Instant?,
    val state: DeviceStateView?,
)

@Service
class DeviceCatalogService(
    private val connections: IntegrationConnectionRepository,
    private val rooms: RoomRepository,
    private val observations: DeviceObservationRepository,
    private val clock: Clock = Clock.systemUTC(),
    private val gateways: GatewayService? = null,
) {
    fun devices(ownerId: UUID): List<DeviceCatalogItem> {
        val ownerRooms = rooms.all(ownerId).associateBy { it.id }
        val ownerObservations = observations.findAll(ownerId).associateBy { it.connectionId }
        val zigbeeDevices = gateways?.all(ownerId).orEmpty().flatMap { it.health?.zigbee?.devices.orEmpty() }
            .associateBy { it.ieeeAddress }
        return connections.findAll(ownerId).map { connection ->
            val observation = ownerObservations[connection.id]
            val currentAvailability = observation?.takeIf { isFresh(it.observedAt) }?.availability
                ?: DeviceAvailability.UNKNOWN
            val zigbee = zigbeeDevices[connection.endpointHost]
            DeviceCatalogItem(
                id = connection.id,
                provider = connection.provider,
                displayName = connection.displayName,
                hardwareName = zigbee?.let { listOf(it.vendor, it.description).filter(String::isNotBlank).joinToString(" ") }
                    ?: if (connection.provider == NanoleafIntegrationService.PROVIDER) "Nanoleaf" else connection.provider,
                room = connection.roomId?.let(ownerRooms::get)?.let { DeviceRoomView(it.id, it.name) },
                capabilities = capabilities(connection),
                availability = currentAvailability,
                observedAt = observation?.observedAt,
                state = zigbee?.let {
                    DeviceStateView(it.on, it.brightness?.let { raw -> (raw * 100 / 254).coerceIn(0, 100) },
                        it.hue, it.saturation, it.colorTemperature)
                },
            )
        }
    }

    private fun isFresh(observedAt: Instant): Boolean {
        val now = clock.instant()
        return !observedAt.isAfter(now) && Duration.between(observedAt, now) <= OBSERVATION_TTL
    }

    private fun capabilities(connection: IntegrationConnection): List<DeviceCapabilityView> = when (connection.provider) {
        NanoleafIntegrationService.PROVIDER -> NANOLEAF_CAPABILITIES.map(::DeviceCapabilityView)
        ZigbeeDeviceSyncService.PROVIDER -> ZIGBEE_CAPABILITIES.map(::DeviceCapabilityView)
        else -> emptyList()
    }

    companion object {
        val OBSERVATION_TTL: Duration = Duration.ofSeconds(60)
        val NANOLEAF_CAPABILITIES = listOf(
            DeviceCommandService.POWER_SET,
            DeviceCommandService.BRIGHTNESS_SET,
            DeviceCommandService.COLOR_SET,
            "light.setColourTemperature",
            "light.activateScene",
        )
        val ZIGBEE_CAPABILITIES = listOf(
            DeviceCommandService.POWER_SET,
            DeviceCommandService.BRIGHTNESS_SET,
            "light.setColour",
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

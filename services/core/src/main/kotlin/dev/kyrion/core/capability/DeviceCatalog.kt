package dev.kyrion.core.capability

import com.fasterxml.jackson.annotation.JsonValue
import dev.kyrion.core.home.RoomRepository
import dev.kyrion.core.integration.IntegrationConnection
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.integration.NanoleafIntegrationService
import dev.kyrion.core.gateway.ZigbeeDeviceSyncService
import dev.kyrion.core.gateway.BluetoothDeviceSyncService
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

data class DeviceRoomView(val id: UUID, val name: String, val roomType: dev.kyrion.core.home.RoomType)
data class DeviceStateView(
    val on: Boolean?,
    val brightness: Int?,
    val hue: Double?,
    val saturation: Double?,
    val colorTemperature: Int?,
    val occupancy: Boolean? = null,
    val battery: Double? = null,
    val illuminance: Double? = null,
    val action: String? = null,
    val illumination: String? = null,
    val temperatureCelsius: Double? = null,
    val relativeHumidity: Double? = null,
    val measuredAt: Instant? = null,
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
    val deviceClass: String,
    val displayName: String,
    val hardwareName: String,
    val room: DeviceRoomView?,
    val capabilities: List<DeviceCapabilityView>,
    val availability: DeviceAvailability,
    val observedAt: Instant?,
    val state: DeviceStateView?,
    val diagnosticReason: String? = null,
)

@Service
class DeviceCatalogService(
    private val connections: IntegrationConnectionRepository,
    private val rooms: RoomRepository,
    private val observations: DeviceObservationRepository,
    private val clock: Clock = Clock.systemUTC(),
    private val gateways: GatewayService? = null,
    private val shellyReadings: dev.kyrion.core.integration.ShellySensorRepository? = null,
    private val importedReadings: dev.kyrion.core.integration.ImportedDeviceRepository? = null,
) {
    fun devices(ownerId: UUID): List<DeviceCatalogItem> {
        val ownerRooms = rooms.all(ownerId).associateBy { it.id }
        val ownerObservations = observations.findAll(ownerId).associateBy { it.connectionId }
        val sensorReadings = shellyReadings?.all(ownerId).orEmpty().associateBy { it.connectionId }
        val imported = importedReadings?.all(ownerId).orEmpty().associateBy { it.connectionId }
        val zigbeeDevices = gateways?.all(ownerId).orEmpty().flatMap { it.health?.zigbee?.devices.orEmpty() }
            .associateBy { it.ieeeAddress }
        val bluetoothDevices = gateways?.all(ownerId).orEmpty().flatMap { it.health?.bluetoothDevices.orEmpty() }
            .associateBy { it.address }
        return connections.findAll(ownerId).map { connection ->
            val observation = ownerObservations[connection.id]
            val currentAvailability = observation?.takeIf { isFresh(it.observedAt) }?.availability
                ?: DeviceAvailability.UNKNOWN
            val zigbee = zigbeeDevices[connection.endpointHost]
            val bluetooth = bluetoothDevices[connection.endpointHost]
            DeviceCatalogItem(
                id = connection.id,
                provider = connection.provider,
                deviceClass = connection.deviceClass.value,
                displayName = connection.displayName,
                hardwareName = imported[connection.id]?.hardwareName ?: zigbee?.let { listOf(it.vendor, it.description).filter(String::isNotBlank).joinToString(" ") }
                    ?: bluetooth?.let { "${it.name} ${it.model}" }
                    ?: if (connection.provider == NanoleafIntegrationService.PROVIDER) "Nanoleaf" else connection.provider,
                room = connection.roomId?.let(ownerRooms::get)?.let { DeviceRoomView(it.id, it.name, it.roomType) },
                capabilities = imported[connection.id]?.capabilities?.map(::DeviceCapabilityView) ?: capabilities(connection, zigbee),
                availability = currentAvailability,
                observedAt = observation?.observedAt,
                diagnosticReason = when {
                    observation == null -> "no_observation"
                    !isFresh(observation.observedAt) -> "stale_observation"
                    currentAvailability == DeviceAvailability.OFFLINE -> "device.offline"
                    currentAvailability == DeviceAvailability.DEGRADED -> "provider.degraded"
                    currentAvailability == DeviceAvailability.UNKNOWN -> "no_observation"
                    else -> null
                },
                state = imported[connection.id]?.state ?: sensorReadings[connection.id]?.takeIf { connection.provider == "shelly" }?.let {
                    DeviceStateView(null, null, null, null, null, battery = it.reading.battery,
                        temperatureCelsius = it.reading.temperatureCelsius, relativeHumidity = it.reading.relativeHumidity,
                        measuredAt = it.observedAt)
                } ?: zigbee?.let {
                    DeviceStateView(it.on, it.brightness?.let { raw -> (raw * 100 / 254).coerceIn(0, 100) },
                        it.hue, it.saturation, it.colorTemperature, it.occupancy, it.battery, it.illuminance, it.action, it.illumination)
                } ?: bluetooth?.let {
                    DeviceStateView(it.on, it.brightness, it.hue, it.saturation, null)
                },
            )
        }
    }

    private fun isFresh(observedAt: Instant): Boolean {
        val now = clock.instant()
        return !observedAt.isAfter(now) && Duration.between(observedAt, now) <= OBSERVATION_TTL
    }

    private fun capabilities(connection: IntegrationConnection, zigbee: dev.kyrion.core.gateway.GatewayZigbeeDevice?): List<DeviceCapabilityView> = when (connection.provider) {
        NanoleafIntegrationService.PROVIDER -> NANOLEAF_CAPABILITIES.map(::DeviceCapabilityView)
        ZigbeeDeviceSyncService.PROVIDER -> zigbeeCapabilities(zigbee).map(::DeviceCapabilityView)
        BluetoothDeviceSyncService.PROVIDER -> BLUETOOTH_CAPABILITIES.map(::DeviceCapabilityView)
        "shelly" -> listOf("temperature.read", "humidity.read", "battery.read").map(::DeviceCapabilityView)
        else -> emptyList()
    }

    private fun zigbeeCapabilities(device: dev.kyrion.core.gateway.GatewayZigbeeDevice?): List<String> = when (device?.model?.uppercase()) {
        "SNZB-03P" -> listOf("occupancy.read", "illumination.read", "battery.read")
        "SNZB-01P" -> listOf("button.events", "battery.read")
        "8720169364066" -> ZIGBEE_LIGHT_CAPABILITIES
        else -> if (device?.on != null || device?.brightness != null) ZIGBEE_LIGHT_CAPABILITIES else emptyList()
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
        val ZIGBEE_LIGHT_CAPABILITIES = listOf(
            DeviceCommandService.POWER_SET,
            DeviceCommandService.BRIGHTNESS_SET,
            "light.setColour",
        )
        val BLUETOOTH_CAPABILITIES = listOf(
            DeviceCommandService.POWER_SET,
            DeviceCommandService.BRIGHTNESS_SET,
            DeviceCommandService.COLOR_SET,
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

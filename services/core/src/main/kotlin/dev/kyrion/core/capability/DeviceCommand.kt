package dev.kyrion.core.capability

import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.home.RoomRepository
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.integration.NanoleafIntegrationService
import dev.kyrion.core.integration.NanoleafUnavailableException
import dev.kyrion.core.gateway.GatewayCommandService
import dev.kyrion.core.gateway.GatewayService
import dev.kyrion.core.gateway.ZigbeeDeviceSyncService
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.Max
import jakarta.validation.constraints.Min
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.bind.annotation.RestControllerAdvice
import java.util.UUID
import java.time.Clock

data class DeviceTargetSelector(
    @field:Size(max = 120) val roomName: String? = null,
    @field:NotBlank @field:Size(max = 60) val provider: String,
    val deviceId: UUID? = null,
)

data class DeviceCommandArguments(
    val on: Boolean? = null,
    @field:Min(0) @field:Max(100) val brightness: Int? = null,
    @field:Min(0) @field:Max(360) val hue: Int? = null,
    @field:Min(0) @field:Max(100) val saturation: Int? = null,
)

data class ExecuteDeviceCommandRequest(
    @field:NotBlank @field:Size(max = 80) val capability: String,
    @field:Valid val selector: DeviceTargetSelector,
    @field:Valid val arguments: DeviceCommandArguments,
)

data class DeviceCommandOutcome(val deviceId: UUID, val displayName: String, val status: String)

data class DeviceCommandResult(
    val capability: String,
    val roomName: String,
    val requested: Int,
    val succeeded: Int,
    val failed: Int,
    val outcomes: List<DeviceCommandOutcome>,
    val correlationId: UUID,
)

@Service
class DeviceCommandService(
    private val rooms: RoomRepository,
    private val connections: IntegrationConnectionRepository,
    private val nanoleaf: NanoleafIntegrationService,
    private val activity: ActivityService,
    private val observations: DeviceObservationRepository,
    private val clock: Clock = Clock.systemUTC(),
    private val gateways: GatewayService? = null,
    private val gatewayCommands: GatewayCommandService? = null,
) {
    fun execute(ownerId: UUID, request: ExecuteDeviceCommandRequest): DeviceCommandResult {
        val provider = request.selector.provider.trim().lowercase()
        if (provider !in setOf(NanoleafIntegrationService.PROVIDER, ZigbeeDeviceSyncService.PROVIDER)) {
            throw DeviceCapabilityUnsupportedException()
        }
        val roomName = request.selector.roomName?.trim()?.takeIf { it.isNotBlank() }
        if ((roomName == null) == (request.selector.deviceId == null)) throw DeviceCommandInvalidException()
        val room = roomName?.let { requestedName ->
            rooms.all(ownerId).singleOrNull { it.name.equals(requestedName, ignoreCase = true) }
                ?: throw DeviceTargetNotFoundException()
        }
        val targets = if (request.selector.deviceId != null) {
            listOfNotNull(connections.find(ownerId, request.selector.deviceId).takeIf { it?.provider == provider })
        } else {
            connections.findAll(ownerId).filter { it.provider == provider && it.roomId == room?.id }
        }
        if (targets.isEmpty()) throw DeviceTargetNotFoundException()

        validateArguments(request)
        val correlationId = UUID.randomUUID()
        activity.record(
            ActivityCategory.CAPABILITY,
            "capability.device.proposed",
            ActivityStatus.PROPOSED,
            ActivityActorType.AI,
            "velora",
            "device.command.proposed",
            ownerId.toString(),
            correlationId,
        )
        val outcomes = targets.map { target ->
            try {
                when (request.capability) {
                    POWER_SET -> if (provider == ZigbeeDeviceSyncService.PROVIDER) {
                        executeZigbee(ownerId, target.endpointHost, "zigbee.power", mapOf("deviceId" to target.endpointHost, "on" to request.arguments.on!!))
                    } else nanoleaf.power(ownerId, target.id, request.arguments.on!!, true, correlationId)
                    BRIGHTNESS_SET -> if (provider == ZigbeeDeviceSyncService.PROVIDER) {
                        executeZigbee(ownerId, target.endpointHost, "zigbee.brightness", mapOf("deviceId" to target.endpointHost, "brightness" to (request.arguments.brightness!! * 254 / 100)))
                    } else nanoleaf.brightness(ownerId, target.id, request.arguments.brightness!!, true, correlationId)
                    COLOR_SET -> if (provider == ZigbeeDeviceSyncService.PROVIDER) {
                        executeZigbee(ownerId, target.endpointHost, "zigbee.color", mapOf("deviceId" to target.endpointHost, "hue" to request.arguments.hue!!, "saturation" to request.arguments.saturation!!))
                    } else throw DeviceCapabilityUnsupportedException()
                }
                observe(ownerId, target.id, DeviceAvailability.ONLINE)
                DeviceCommandOutcome(target.id, target.displayName, "succeeded")
            } catch (_: NanoleafUnavailableException) {
                observe(ownerId, target.id, DeviceAvailability.OFFLINE)
                DeviceCommandOutcome(target.id, target.displayName, "unavailable")
            } catch (_: RuntimeException) {
                observe(ownerId, target.id, DeviceAvailability.DEGRADED)
                DeviceCommandOutcome(target.id, target.displayName, "failed")
            }
        }
        val succeeded = outcomes.count { it.status == "succeeded" }
        return DeviceCommandResult(
            request.capability,
            room?.name ?: targets.single().roomId?.let { rooms.find(ownerId, it)?.name } ?: "Unassigned",
            outcomes.size,
            succeeded,
            outcomes.size - succeeded,
            outcomes,
            correlationId,
        )
    }

    private fun executeZigbee(ownerId: UUID, ieeeAddress: String, type: String, payload: Map<String, Any>) {
        val node = gateways?.all(ownerId)?.singleOrNull { view ->
            view.health?.zigbee?.devices?.any { it.ieeeAddress == ieeeAddress } == true
        } ?: throw DeviceTargetNotFoundException()
        if (gatewayCommands?.enqueueAndAwait(ownerId, node.id, type, payload) != true) throw RuntimeException("Gateway command failed")
    }

    private fun observe(ownerId: UUID, connectionId: UUID, availability: DeviceAvailability) {
        try {
            observations.save(DeviceObservation(connectionId, ownerId, availability, clock.instant()))
        } catch (_: RuntimeException) {
            // Observation persistence must not turn a confirmed physical command into a false failure.
        }
    }

    private fun validateArguments(request: ExecuteDeviceCommandRequest) {
        when (request.capability) {
            POWER_SET -> if (request.arguments.on == null || request.arguments.brightness != null || request.arguments.hue != null || request.arguments.saturation != null) throw DeviceCommandInvalidException()
            BRIGHTNESS_SET -> if (request.arguments.brightness == null || request.arguments.on != null || request.arguments.hue != null || request.arguments.saturation != null) throw DeviceCommandInvalidException()
            COLOR_SET -> if (request.arguments.hue == null || request.arguments.saturation == null || request.arguments.on != null || request.arguments.brightness != null) throw DeviceCommandInvalidException()
            else -> throw DeviceCapabilityUnsupportedException()
        }
    }

    companion object {
        const val POWER_SET = "power.set"
        const val BRIGHTNESS_SET = "light.setBrightness"
        const val COLOR_SET = "light.setColour"
    }
}

@RestController
@RequestMapping("/v1/device-commands")
class DeviceCommandController(private val commands: DeviceCommandService) {
    @PostMapping
    fun execute(@Valid @RequestBody body: ExecuteDeviceCommandRequest, request: HttpServletRequest) =
        commands.execute(request.ownerId(), body)

    private fun HttpServletRequest.ownerId() =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw DeviceCommandUnauthenticatedException()
}

class DeviceTargetNotFoundException : RuntimeException()
class DeviceCapabilityUnsupportedException : RuntimeException()
class DeviceCommandInvalidException : RuntimeException()
class DeviceCommandUnauthenticatedException : RuntimeException()

@RestControllerAdvice
class DeviceCommandErrorHandler {
    @ExceptionHandler(DeviceTargetNotFoundException::class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    fun targetNotFound() = mapOf("code" to "DEVICE_TARGET_NOT_FOUND")

    @ExceptionHandler(DeviceCapabilityUnsupportedException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun unsupported() = mapOf("code" to "DEVICE_CAPABILITY_UNSUPPORTED")

    @ExceptionHandler(DeviceCommandInvalidException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid() = mapOf("code" to "DEVICE_COMMAND_INVALID")

    @ExceptionHandler(DeviceCommandUnauthenticatedException::class)
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    fun unauthenticated() = mapOf("code" to "UNAUTHENTICATED")
}

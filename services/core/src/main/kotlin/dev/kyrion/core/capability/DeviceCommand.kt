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
import dev.kyrion.core.gateway.BluetoothDeviceSyncService
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
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
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
data class AsyncDeviceCommandResult(val commandId: UUID, val deviceId: UUID, val status: String = "pending")

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
    fun enqueue(ownerId: UUID, request: ExecuteDeviceCommandRequest): AsyncDeviceCommandResult {
        val provider = request.selector.provider.trim().lowercase()
        if (provider !in setOf(ZigbeeDeviceSyncService.PROVIDER, BluetoothDeviceSyncService.PROVIDER)
            || request.selector.deviceId == null || request.selector.roomName != null) throw DeviceCommandInvalidException()
        validateArguments(request)
        val target = connections.find(ownerId, request.selector.deviceId)
            ?.takeIf { it.provider == provider } ?: throw DeviceTargetNotFoundException()
        val node = gateways?.all(ownerId)?.singleOrNull { view ->
            if (provider == ZigbeeDeviceSyncService.PROVIDER) {
                view.health?.zigbee?.devices?.any { it.ieeeAddress == target.endpointHost } == true
            } else {
                view.health?.bluetoothDevices?.any { it.address == target.endpointHost } == true
            }
        } ?: throw DeviceTargetNotFoundException()
        val (type, payload) = when (request.capability) {
            POWER_SET -> "$provider.power" to mapOf("deviceId" to target.endpointHost, "on" to request.arguments.on!!)
            BRIGHTNESS_SET -> "$provider.brightness" to mapOf(
                "deviceId" to target.endpointHost,
                "brightness" to if (provider == ZigbeeDeviceSyncService.PROVIDER) {
                    request.arguments.brightness!! * 254 / 100
                } else request.arguments.brightness!!,
            )
            COLOR_SET -> "$provider.color" to mapOf("deviceId" to target.endpointHost, "hue" to request.arguments.hue!!, "saturation" to request.arguments.saturation!!)
            else -> throw DeviceCapabilityUnsupportedException()
        }
        val commandId = gatewayCommands?.enqueue(ownerId, node.id, type, payload) ?: throw DeviceCommandInvalidException()
        return AsyncDeviceCommandResult(commandId, target.id)
    }

    fun status(ownerId: UUID, id: UUID) = gatewayCommands?.status(ownerId, id) ?: throw DeviceCommandInvalidException()

    fun execute(
        ownerId: UUID,
        request: ExecuteDeviceCommandRequest,
        correlationId: UUID = UUID.randomUUID(),
        recordProposal: Boolean = true,
    ): DeviceCommandResult {
        val provider = request.selector.provider.trim().lowercase()
        if (provider !in setOf(NanoleafIntegrationService.PROVIDER, ZigbeeDeviceSyncService.PROVIDER, BluetoothDeviceSyncService.PROVIDER)) {
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
        if (recordProposal) {
            activity.record(
                ActivityCategory.CAPABILITY,
                "capability.device.proposed",
                ActivityStatus.PROPOSED,
                ActivityActorType.AI,
                "velora",
                "device.command.proposed",
                ownerId.toString(),
                correlationId,
                ownerId,
            )
        }
        val outcomes = targets.map { target ->
            try {
                when (request.capability) {
                    POWER_SET -> if (provider != NanoleafIntegrationService.PROVIDER) {
                        executeGateway(ownerId, provider, target.endpointHost, "$provider.power", mapOf("deviceId" to target.endpointHost, "on" to request.arguments.on!!))
                    } else nanoleaf.power(ownerId, target.id, request.arguments.on!!, true, correlationId)
                    BRIGHTNESS_SET -> if (provider != NanoleafIntegrationService.PROVIDER) {
                        val value = if (provider == ZigbeeDeviceSyncService.PROVIDER) request.arguments.brightness!! * 254 / 100 else request.arguments.brightness!!
                        executeGateway(ownerId, provider, target.endpointHost, "$provider.brightness", mapOf("deviceId" to target.endpointHost, "brightness" to value))
                    } else nanoleaf.brightness(ownerId, target.id, request.arguments.brightness!!, true, correlationId)
                    COLOR_SET -> if (provider != NanoleafIntegrationService.PROVIDER) {
                        executeGateway(ownerId, provider, target.endpointHost, "$provider.color", mapOf("deviceId" to target.endpointHost, "hue" to request.arguments.hue!!, "saturation" to request.arguments.saturation!!))
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

    private fun executeGateway(ownerId: UUID, provider: String, deviceAddress: String, type: String, payload: Map<String, Any>) {
        val node = gateways?.all(ownerId)?.singleOrNull { view ->
            if (provider == ZigbeeDeviceSyncService.PROVIDER) {
                view.health?.zigbee?.devices?.any { it.ieeeAddress == deviceAddress } == true
            } else {
                view.health?.bluetoothDevices?.any { it.address == deviceAddress } == true
            }
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

    @PostMapping("/async")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun enqueue(@Valid @RequestBody body: ExecuteDeviceCommandRequest, request: HttpServletRequest) =
        commands.enqueue(request.ownerId(), body)

    @GetMapping("/{id}")
    fun status(@PathVariable id: UUID, request: HttpServletRequest) = commands.status(request.ownerId(), id)

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

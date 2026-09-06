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
import dev.kyrion.core.security.workspaceOwnerId
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
import java.util.concurrent.ConcurrentHashMap

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
class CommandedPowerStateStore {
    private val states = ConcurrentHashMap<Pair<UUID, UUID>, Boolean>()

    fun get(ownerId: UUID, deviceId: UUID): Boolean? = states[ownerId to deviceId]

    fun record(ownerId: UUID, deviceId: UUID, on: Boolean) {
        states[ownerId to deviceId] = on
    }
}

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
    private val powerStates: CommandedPowerStateStore = CommandedPowerStateStore(),
    private val catalog: DeviceCatalogService? = null,
) {
    fun enqueue(ownerId: UUID, request: ExecuteDeviceCommandRequest): AsyncDeviceCommandResult {
        val correlationId = UUID.randomUUID()
        activity.record(ActivityCategory.CAPABILITY, "action.request.received", ActivityStatus.PROPOSED,
            ActivityActorType.USER, "web", "action.proposed", ownerId.toString(), correlationId, ownerId)
        try {
            val provider = request.selector.provider.trim().lowercase()
            if (provider !in setOf(ZigbeeDeviceSyncService.PROVIDER, BluetoothDeviceSyncService.PROVIDER)
                || request.selector.deviceId == null || request.selector.roomName != null) throw DeviceCommandInvalidException()
            validateArguments(request)
            val target = connections.find(ownerId, request.selector.deviceId)
                ?.takeIf { it.provider == provider } ?: throw DeviceTargetNotFoundException()
            requireCapability(ownerId, target.id, request.capability)
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
            activity.record(ActivityCategory.CAPABILITY, "action.capability", ActivityStatus.PROPOSED,
                ActivityActorType.USER, "web", request.capability, ownerId.toString(), correlationId, ownerId)
            activity.record(ActivityCategory.CAPABILITY, "action.target.resolved", ActivityStatus.CONFIRMED,
                ActivityActorType.USER, "web", target.id.toString(), ownerId.toString(), correlationId, ownerId)
            activity.record(ActivityCategory.CAPABILITY, "action.policy.accepted", ActivityStatus.CONFIRMED,
                ActivityActorType.USER, "web", "routine", ownerId.toString(), correlationId, ownerId)
            activity.record(ActivityCategory.CAPABILITY, "action.adapter.invoked", ActivityStatus.CONFIRMED,
                ActivityActorType.USER, provider, target.id.toString(), ownerId.toString(), correlationId, ownerId)
            val commandId = gatewayCommands?.enqueue(ownerId, node.id, type, payload, correlationId) ?: throw DeviceCommandInvalidException()
            return AsyncDeviceCommandResult(commandId, target.id)
        } catch (exception: RuntimeException) {
            val code = when (exception) {
                is DeviceTargetNotFoundException -> "target.not_found"
                is DeviceCapabilityUnsupportedException -> "action.unsupported"
                is dev.kyrion.core.gateway.GatewayCommandUnavailableException -> "adapter.offline"
                else -> "proposal.invalid"
            }
            activity.record(ActivityCategory.CAPABILITY, "action.rejected", ActivityStatus.DENIED,
                ActivityActorType.USER, "web", code, ownerId.toString(), correlationId, ownerId)
            throw exception
        }
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
        targets.forEach { requireCapability(ownerId, it.id, request.capability) }

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
            activity.record(ActivityCategory.CAPABILITY, "action.adapter.invoked", ActivityStatus.CONFIRMED,
                ActivityActorType.USER, provider, target.id.toString(), ownerId.toString(), correlationId, ownerId)
            try {
                when (request.capability) {
                    POWER_SET -> if (provider != NanoleafIntegrationService.PROVIDER) {
                        executeGateway(ownerId, provider, target.endpointHost, "$provider.power", mapOf("deviceId" to target.endpointHost, "on" to request.arguments.on!!), correlationId)
                    } else nanoleaf.power(ownerId, target.id, request.arguments.on!!, true, correlationId)
                    BRIGHTNESS_SET -> if (provider != NanoleafIntegrationService.PROVIDER) {
                        val value = if (provider == ZigbeeDeviceSyncService.PROVIDER) request.arguments.brightness!! * 254 / 100 else request.arguments.brightness!!
                        executeGateway(ownerId, provider, target.endpointHost, "$provider.brightness", mapOf("deviceId" to target.endpointHost, "brightness" to value), correlationId)
                    } else nanoleaf.brightness(ownerId, target.id, request.arguments.brightness!!, true, correlationId)
                    COLOR_SET -> if (provider != NanoleafIntegrationService.PROVIDER) {
                        executeGateway(ownerId, provider, target.endpointHost, "$provider.color", mapOf("deviceId" to target.endpointHost, "hue" to request.arguments.hue!!, "saturation" to request.arguments.saturation!!), correlationId)
                    } else nanoleaf.color(ownerId, target.id, request.arguments.hue!! % 360, request.arguments.saturation!!, true, correlationId)
                }
                if (request.capability == POWER_SET) {
                    powerStates.record(ownerId, target.id, request.arguments.on!!)
                }
                observe(ownerId, target.id, DeviceAvailability.ONLINE)
                // Audit storage failure after physical execution must not change a confirmed result.
                runCatching {
                    activity.record(ActivityCategory.CAPABILITY, "action.device.confirmed", ActivityStatus.SUCCEEDED,
                        ActivityActorType.INTEGRATION, provider, target.id.toString(), ownerId.toString(), correlationId, ownerId)
                }
                DeviceCommandOutcome(target.id, target.displayName, "succeeded")
            } catch (_: NanoleafUnavailableException) {
                observe(ownerId, target.id, DeviceAvailability.OFFLINE)
                recordFailure(ownerId, provider, correlationId, "device.offline")
                DeviceCommandOutcome(target.id, target.displayName, "unavailable")
            } catch (_: dev.kyrion.core.gateway.GatewayCommandUnavailableException) {
                observe(ownerId, target.id, DeviceAvailability.OFFLINE)
                recordFailure(ownerId, provider, correlationId, "adapter.offline")
                DeviceCommandOutcome(target.id, target.displayName, "unavailable")
            } catch (exception: dev.kyrion.core.gateway.GatewayExecutionException) {
                observe(ownerId, target.id, DeviceAvailability.DEGRADED)
                recordFailure(ownerId, provider, correlationId, exception.code)
                DeviceCommandOutcome(target.id, target.displayName, "failed")
            } catch (_: dev.kyrion.core.integration.NanoleafInvalidResponseException) {
                observe(ownerId, target.id, DeviceAvailability.DEGRADED)
                recordFailure(ownerId, provider, correlationId, "adapter.invalid_result")
                DeviceCommandOutcome(target.id, target.displayName, "failed")
            } catch (_: RuntimeException) {
                observe(ownerId, target.id, DeviceAvailability.DEGRADED)
                recordFailure(ownerId, provider, correlationId, "adapter.failed")
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

    private fun recordFailure(ownerId: UUID, provider: String, correlationId: UUID, code: String) {
        activity.record(ActivityCategory.CAPABILITY, "action.adapter.failed", ActivityStatus.FAILED,
            ActivityActorType.INTEGRATION, provider, code, ownerId.toString(), correlationId, ownerId)
    }

    private fun requireCapability(ownerId: UUID, deviceId: UUID, capability: String) {
        val device = catalog?.devices(ownerId)?.singleOrNull { it.id == deviceId } ?: if (catalog == null) return else throw DeviceTargetNotFoundException()
        if (device.capabilities.none { it.id == capability }) throw DeviceCapabilityUnsupportedException()
    }

    private fun executeGateway(ownerId: UUID, provider: String, deviceAddress: String, type: String, payload: Map<String, Any>, correlationId: UUID) {
        val node = gateways?.all(ownerId)?.singleOrNull { view ->
            if (provider == ZigbeeDeviceSyncService.PROVIDER) {
                view.health?.zigbee?.devices?.any { it.ieeeAddress == deviceAddress } == true
            } else {
                view.health?.bluetoothDevices?.any { it.address == deviceAddress } == true
            }
        } ?: throw DeviceTargetNotFoundException()
        val commands = gatewayCommands ?: throw dev.kyrion.core.gateway.GatewayCommandUnavailableException()
        commands.executeConfirmed(ownerId, node.id, type, payload, correlationId)
    }

    private fun observe(ownerId: UUID, connectionId: UUID, availability: DeviceAvailability) {
        try {
            observations.save(DeviceObservation(connectionId, ownerId, availability, clock.instant()))
        } catch (_: RuntimeException) {
            // Observation persistence must not turn a confirmed physical command into a false failure.
        }
    }

    private fun validateArguments(request: ExecuteDeviceCommandRequest) {
        if (request.arguments.brightness?.let { it !in 0..100 } == true || request.arguments.hue?.let { it !in 0..360 } == true ||
            request.arguments.saturation?.let { it !in 0..100 } == true) throw DeviceCommandInvalidException()
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

    private fun HttpServletRequest.ownerId() = workspaceOwnerId()
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

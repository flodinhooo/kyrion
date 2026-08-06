package dev.kyrion.core.gateway

import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Pattern
import jakarta.validation.constraints.Size
import jakarta.validation.constraints.Max
import jakarta.validation.constraints.Min
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestHeader
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.bind.annotation.RestControllerAdvice
import java.util.UUID

data class CreateGatewayEnrollmentRequest(@field:NotBlank @field:Size(max = 120) val displayName: String)
data class GatewayEnrollmentResponse(val id: UUID, val enrollmentToken: String, val expiresAt: java.time.Instant)
data class GatewayEnrollRequest(
    @field:NotBlank @field:Size(max = 200) val enrollmentToken: String,
    @field:NotBlank @field:Size(max = 253) @field:Pattern(regexp = "^[A-Za-z0-9.-]+$") val hostname: String,
    @field:NotBlank @field:Size(max = 40) val agentVersion: String,
    @field:NotBlank @field:Size(max = 120) val osName: String,
    @field:NotBlank @field:Size(max = 80) val osVersion: String,
    @field:NotBlank @field:Size(max = 40) val architecture: String,
)
data class GatewayEnrollResponse(val nodeId: UUID, val gatewayToken: String)
data class GatewayHeartbeatRequest(@field:Valid val health: GatewayHealth)
data class ZigbeePairingRequest(@field:Min(0) @field:Max(254) val duration: Int)
data class ZigbeeCommandRequest(
    @field:Pattern(regexp = "^0x[0-9a-f]{16}$") val deviceId: String,
    val on: Boolean? = null,
    @field:Min(0) @field:Max(254) val brightness: Int? = null,
    @field:Min(0) @field:Max(360) val hue: Int? = null,
    @field:Min(0) @field:Max(100) val saturation: Int? = null,
)
data class GatewayCommandResponse(val id: UUID)
data class GatewayCommandResultRequest(val succeeded: Boolean, @field:Size(max = 80) val error: String?)

@RestController
@RequestMapping("/v1/gateways")
class GatewayOwnerController(private val service: GatewayService, private val commands: GatewayCommandService) {
    @GetMapping fun all(request: HttpServletRequest) = service.all(request.ownerId())

    @PostMapping("/enrollments")
    @ResponseStatus(HttpStatus.CREATED)
    fun createEnrollment(@Valid @RequestBody body: CreateGatewayEnrollmentRequest, request: HttpServletRequest): GatewayEnrollmentResponse {
        val created = service.createEnrollment(request.ownerId(), body.displayName.trim())
        return GatewayEnrollmentResponse(created.id, created.enrollmentToken, created.expiresAt)
    }

    @PostMapping("/{id}/zigbee/pairing")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun pairing(@PathVariable id: UUID, @Valid @RequestBody body: ZigbeePairingRequest, request: HttpServletRequest) =
        GatewayCommandResponse(commands.enqueue(request.ownerId(), id, "zigbee.permit_join", mapOf("duration" to body.duration)))

    @PostMapping("/{id}/zigbee/power") @ResponseStatus(HttpStatus.ACCEPTED)
    fun power(@PathVariable id: UUID, @Valid @RequestBody body: ZigbeeCommandRequest, request: HttpServletRequest): GatewayCommandResponse {
        val on = body.on ?: throw GatewayCommandInvalidException()
        return GatewayCommandResponse(commands.enqueue(request.ownerId(), id, "zigbee.power", mapOf("deviceId" to body.deviceId, "on" to on)))
    }

    @PostMapping("/{id}/zigbee/brightness") @ResponseStatus(HttpStatus.ACCEPTED)
    fun brightness(@PathVariable id: UUID, @Valid @RequestBody body: ZigbeeCommandRequest, request: HttpServletRequest): GatewayCommandResponse {
        val value = body.brightness ?: throw GatewayCommandInvalidException()
        return GatewayCommandResponse(commands.enqueue(request.ownerId(), id, "zigbee.brightness", mapOf("deviceId" to body.deviceId, "brightness" to value)))
    }

    @PostMapping("/{id}/zigbee/color") @ResponseStatus(HttpStatus.ACCEPTED)
    fun color(@PathVariable id: UUID, @Valid @RequestBody body: ZigbeeCommandRequest, request: HttpServletRequest): GatewayCommandResponse {
        val hue = body.hue ?: throw GatewayCommandInvalidException()
        val saturation = body.saturation ?: throw GatewayCommandInvalidException()
        return GatewayCommandResponse(commands.enqueue(request.ownerId(), id, "zigbee.color", mapOf("deviceId" to body.deviceId, "hue" to hue, "saturation" to saturation)))
    }

    private fun HttpServletRequest.ownerId() =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw GatewayUnauthenticatedException()
}

@RestController
@RequestMapping("/v1/gateway-agent")
class GatewayAgentController(private val service: GatewayService, private val commands: GatewayCommandService) {
    @PostMapping("/enroll")
    @ResponseStatus(HttpStatus.CREATED)
    fun enroll(@Valid @RequestBody body: GatewayEnrollRequest): GatewayEnrollResponse {
        val registered = service.enroll(
            body.enrollmentToken, body.hostname.lowercase(), body.agentVersion,
            body.osName, body.osVersion, body.architecture,
        )
        return GatewayEnrollResponse(registered.node.id, registered.gatewayToken)
    }

    @PutMapping("/heartbeat")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun heartbeat(
        @RequestHeader("X-Kyrion-Node-Id") nodeId: UUID,
        @RequestHeader("Authorization") authorization: String,
        @Valid @RequestBody body: GatewayHeartbeatRequest,
    ) {
        if (!authorization.startsWith("Bearer ") || authorization.length <= 7) throw GatewayUnauthenticatedException()
        service.heartbeat(nodeId, authorization.substring(7), body.health)
    }

    @PostMapping("/commands/next")
    fun nextCommand(@RequestHeader("X-Kyrion-Node-Id") nodeId: UUID, @RequestHeader("Authorization") authorization: String): GatewayCommand? {
        if (!authorization.startsWith("Bearer ")) throw GatewayUnauthenticatedException()
        return commands.next(nodeId, authorization.substring(7))
    }

    @PostMapping("/commands/{id}/result") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun commandResult(@PathVariable id: UUID, @RequestHeader("X-Kyrion-Node-Id") nodeId: UUID,
        @RequestHeader("Authorization") authorization: String, @Valid @RequestBody body: GatewayCommandResultRequest) {
        if (!authorization.startsWith("Bearer ")) throw GatewayUnauthenticatedException()
        commands.complete(nodeId, authorization.substring(7), id, body.succeeded, body.error)
    }
}

@RestControllerAdvice
class GatewayErrorHandler {
    @ExceptionHandler(GatewayEnrollmentInvalidException::class)
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    fun invalidEnrollment() = mapOf("code" to "GATEWAY_ENROLLMENT_INVALID")

    @ExceptionHandler(GatewayAlreadyRegisteredException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun alreadyRegistered() = mapOf("code" to "GATEWAY_ALREADY_REGISTERED")

    @ExceptionHandler(GatewayUnauthenticatedException::class)
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    fun unauthenticated() = mapOf("code" to "GATEWAY_UNAUTHENTICATED")

    @ExceptionHandler(GatewayHealthInvalidException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalidHealth() = mapOf("code" to "GATEWAY_HEALTH_INVALID")

    @ExceptionHandler(GatewayCommandInvalidException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalidCommand() = mapOf("code" to "GATEWAY_COMMAND_INVALID")

    @ExceptionHandler(GatewayCommandUnavailableException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun unavailableCommand() = mapOf("code" to "GATEWAY_UNAVAILABLE")
}

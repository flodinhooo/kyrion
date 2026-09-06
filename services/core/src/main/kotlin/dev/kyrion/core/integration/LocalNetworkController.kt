package dev.kyrion.core.integration

import dev.kyrion.core.security.workspaceOwnerId
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*
import java.util.UUID

data class ConnectShellyRequest(
    @field:NotBlank @field:Size(max = 45) val host: String,
    @field:Size(max = 160) val displayName: String? = null,
    val confirmed: Boolean = false,
)

@RestController
@RequestMapping("/v1/integrations")
class LocalNetworkController(
    private val discovery: LocalNetworkDiscovery,
    private val shelly: ShellyIntegrationService,
    private val connections: IntegrationConnectionRepository,
) {
    @PostMapping("/network/discover")
    fun discover(request: HttpServletRequest): List<DiscoveredNetworkDevice> {
        val ownerId = request.ownerId()
        val devices = try { discovery.discover() } catch (_: java.io.IOException) { throw ShellyException("NETWORK_DISCOVERY_UNAVAILABLE") }
        return markConnectedNetworkDevices(ownerId, devices, connections.findAll(ownerId))
    }

    @PostMapping("/shelly/connections")
    @ResponseStatus(HttpStatus.CREATED)
    fun connect(@Valid @RequestBody body: ConnectShellyRequest, request: HttpServletRequest) =
        shelly.connect(request.ownerId(), body.host, body.displayName, body.confirmed)

    private fun HttpServletRequest.ownerId() = workspaceOwnerId()
}

internal fun markConnectedNetworkDevices(ownerId: UUID, devices: List<DiscoveredNetworkDevice>, connections: List<IntegrationConnection>): List<DiscoveredNetworkDevice> {
    val owned = connections.filter { it.ownerId == ownerId && it.provider in setOf("nanoleaf", "shelly") }
    return devices.map { device -> device.copy(connected = owned.any {
        it.endpointHost == device.host && (device.provider == "network" || it.provider == device.provider)
    }) }
}

@RestControllerAdvice
class ShellyErrorHandler {
    @ExceptionHandler(ShellyException::class)
    fun error(exception: ShellyException): ResponseEntity<Map<String, String>> = ResponseEntity
        .status(if (exception.code in setOf("SHELLY_AUTH_REQUIRED", "SHELLY_UNSUPPORTED_DEVICE")) 409 else 502)
        .body(mapOf("code" to exception.code))
}

package dev.kyrion.core.integration

import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
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
class LocalNetworkController(private val discovery: LocalNetworkDiscovery, private val shelly: ShellyIntegrationService) {
    @PostMapping("/network/discover")
    fun discover(request: HttpServletRequest): List<DiscoveredNetworkDevice> {
        request.ownerId()
        return try { discovery.discover() } catch (_: java.io.IOException) { throw ShellyException("NETWORK_DISCOVERY_UNAVAILABLE") }
    }

    @PostMapping("/shelly/connections")
    @ResponseStatus(HttpStatus.CREATED)
    fun connect(@Valid @RequestBody body: ConnectShellyRequest, request: HttpServletRequest) =
        shelly.connect(request.ownerId(), body.host, body.displayName, body.confirmed)

    private fun HttpServletRequest.ownerId() =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw IntegrationUnauthenticatedException()
}

@RestControllerAdvice
class ShellyErrorHandler {
    @ExceptionHandler(ShellyException::class)
    fun error(exception: ShellyException): ResponseEntity<Map<String, String>> = ResponseEntity
        .status(if (exception.code in setOf("SHELLY_AUTH_REQUIRED", "SHELLY_UNSUPPORTED_DEVICE")) 409 else 502)
        .body(mapOf("code" to exception.code))
}

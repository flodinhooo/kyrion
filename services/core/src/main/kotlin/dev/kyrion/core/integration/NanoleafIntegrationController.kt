package dev.kyrion.core.integration

import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.*
import java.util.UUID

data class PairNanoleafRequest(
    @field:NotBlank @field:Size(max = 45) val host: String,
    @field:Size(max = 160) val displayName: String? = null,
)
data class NanoleafPowerRequest(val on: Boolean, val confirmed: Boolean)
data class NanoleafBrightnessRequest(val brightness: Int, val confirmed: Boolean)
data class RenameIntegrationRequest(@field:NotBlank @field:Size(max = 160) val displayName: String)

@RestController
@RequestMapping("/v1/integrations/nanoleaf")
class NanoleafIntegrationController(
    private val service: NanoleafIntegrationService,
    private val discovery: NanoleafDiscovery,
) {
    @GetMapping("/discover") fun discover() = discovery.discover()
    @GetMapping("/connections") fun connections(request: HttpServletRequest) = service.connections(request.ownerId())

    @PostMapping("/connections") @ResponseStatus(HttpStatus.CREATED)
    fun pair(@Valid @RequestBody body: PairNanoleafRequest, request: HttpServletRequest) =
        service.pair(request.ownerId(), body.host, body.displayName)

    @GetMapping("/connections/{id}/state")
    fun state(@PathVariable id: UUID, request: HttpServletRequest) = service.state(request.ownerId(), id)

    @PatchMapping("/connections/{id}")
    fun rename(@PathVariable id: UUID, @Valid @RequestBody body: RenameIntegrationRequest, request: HttpServletRequest) =
        service.rename(request.ownerId(), id, body.displayName)

    @PutMapping("/connections/{id}/power")
    fun power(@PathVariable id: UUID, @RequestBody body: NanoleafPowerRequest, request: HttpServletRequest) =
        service.power(request.ownerId(), id, body.on, body.confirmed)

    @PutMapping("/connections/{id}/brightness")
    fun brightness(@PathVariable id: UUID, @RequestBody body: NanoleafBrightnessRequest, request: HttpServletRequest) =
        service.brightness(request.ownerId(), id, body.brightness, body.confirmed)

    @DeleteMapping("/connections/{id}") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun remove(@PathVariable id: UUID, request: HttpServletRequest) = service.remove(request.ownerId(), id)

    private fun HttpServletRequest.ownerId(): UUID =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw IntegrationUnauthenticatedException()
}

class IntegrationUnauthenticatedException : RuntimeException()

@RestControllerAdvice
class IntegrationErrorHandler {
    @ExceptionHandler(IntegrationNotFoundException::class) @ResponseStatus(HttpStatus.NOT_FOUND)
    fun notFound() = mapOf("code" to "INTEGRATION_NOT_FOUND")
    @ExceptionHandler(IntegrationInvalidHostException::class) @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalidHost() = mapOf("code" to "INTEGRATION_INVALID_HOST")
    @ExceptionHandler(IntegrationConfirmationRequiredException::class) @ResponseStatus(HttpStatus.CONFLICT)
    fun confirmation() = mapOf("code" to "CONFIRMATION_REQUIRED")
    @ExceptionHandler(IntegrationInvalidNameException::class, IntegrationInvalidBrightnessException::class) @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalidValue() = mapOf("code" to "INVALID_REQUEST")
    @ExceptionHandler(NanoleafPairingWindowClosedException::class) @ResponseStatus(HttpStatus.CONFLICT)
    fun pairingWindow() = mapOf("code" to "NANOLEAF_PAIRING_WINDOW_CLOSED")
    @ExceptionHandler(NanoleafUnavailableException::class) @ResponseStatus(HttpStatus.BAD_GATEWAY)
    fun unavailable() = mapOf("code" to "NANOLEAF_UNAVAILABLE")
    @ExceptionHandler(NanoleafInvalidResponseException::class) @ResponseStatus(HttpStatus.BAD_GATEWAY)
    fun invalidResponse() = mapOf("code" to "NANOLEAF_INVALID_RESPONSE")
    @ExceptionHandler(IntegrationUnauthenticatedException::class) @ResponseStatus(HttpStatus.UNAUTHORIZED)
    fun unauthenticated() = mapOf("code" to "UNAUTHENTICATED")
}

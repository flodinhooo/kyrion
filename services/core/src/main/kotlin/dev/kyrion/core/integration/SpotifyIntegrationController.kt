package dev.kyrion.core.integration

import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.*
import java.util.UUID
import java.math.BigDecimal

data class CompleteSpotifyAuthorizationRequest(@field:NotBlank @field:Size(max = 2048) val code: String, @field:NotBlank @field:Size(max = 256) val state: String)
data class TransferSpotifyPlaybackRequest(@field:NotBlank @field:Size(max = 200) val deviceId: String, val play: Boolean = true)
data class ControlSpotifyPlaybackRequest(
    val action: SpotifyPlaybackAction,
    @field:NotBlank @field:Size(max = 200) val deviceId: String,
    val volumePercent: BigDecimal? = null,
) {
    fun command() = SpotifyPlaybackCommand(action, deviceId, try { volumePercent?.intValueExact() } catch (_: ArithmeticException) { throw SpotifyInvalidRequestException() })
}

@RestController
@RequestMapping("/v1/integrations/spotify")
class SpotifyIntegrationController(private val service: SpotifyIntegrationService) {
    @GetMapping fun status(request: HttpServletRequest) = service.status(request.ownerId())
    @PostMapping("/authorization") fun authorize(request: HttpServletRequest) = service.authorize(request.ownerId())
    @PostMapping("/authorization/complete") fun complete(@Valid @RequestBody body: CompleteSpotifyAuthorizationRequest, request: HttpServletRequest) = service.complete(request.ownerId(), body.code, body.state)
    @GetMapping("/devices") fun devices(request: HttpServletRequest) = service.devices(request.ownerId())
    @GetMapping("/playback") fun playback(request: HttpServletRequest) = service.playback(request.ownerId())
    @PutMapping("/playback") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun control(@Valid @RequestBody body: ControlSpotifyPlaybackRequest, request: HttpServletRequest) = service.control(request.ownerId(), body.command())
    @PutMapping("/playback/device") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun transfer(@Valid @RequestBody body: TransferSpotifyPlaybackRequest, request: HttpServletRequest) = service.transfer(request.ownerId(), body.deviceId, body.play)
    @DeleteMapping @ResponseStatus(HttpStatus.NO_CONTENT) fun disconnect(request: HttpServletRequest) = service.disconnect(request.ownerId())
    private fun HttpServletRequest.ownerId() = getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw IntegrationUnauthenticatedException()
}

@RestControllerAdvice
class SpotifyErrorHandler {
    @ExceptionHandler(SpotifyNotConfiguredException::class) @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE) fun notConfigured() = mapOf("code" to "SPOTIFY_NOT_CONFIGURED")
    @ExceptionHandler(SpotifyInvalidStateException::class) @ResponseStatus(HttpStatus.BAD_REQUEST) fun invalidState() = mapOf("code" to "SPOTIFY_INVALID_STATE")
    @ExceptionHandler(SpotifyInvalidRequestException::class) @ResponseStatus(HttpStatus.BAD_REQUEST) fun invalidRequest() = mapOf("code" to "INVALID_REQUEST")
    @ExceptionHandler(SpotifyUnavailableException::class) @ResponseStatus(HttpStatus.BAD_GATEWAY) fun unavailable() = mapOf("code" to "SPOTIFY_UNAVAILABLE")
    @ExceptionHandler(SpotifyInvalidResponseException::class) @ResponseStatus(HttpStatus.BAD_GATEWAY) fun invalidResponse() = mapOf("code" to "SPOTIFY_INVALID_RESPONSE")
    @ExceptionHandler(SpotifyProviderException::class) fun provider(error: SpotifyProviderException) = org.springframework.http.ResponseEntity.status(if (error.providerStatus == 429) 429 else 502).body(mapOf("code" to if (error.providerStatus == 403) "SPOTIFY_PREMIUM_REQUIRED" else "SPOTIFY_PROVIDER_ERROR"))
}

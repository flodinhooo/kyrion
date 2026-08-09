package dev.kyrion.core.voice

import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Pattern
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestHeader
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.bind.annotation.RestControllerAdvice
import java.time.Instant
import java.util.UUID

data class CreateVoiceEnrollmentRequest(@field:NotBlank @field:Size(max = 120) val displayName: String)
data class VoiceEnrollmentResponse(val id: UUID, val enrollmentToken: String, val expiresAt: Instant)
data class EnrollVoiceSatelliteRequest(
    @field:NotBlank @field:Size(max = 200) val enrollmentToken: String,
    @field:NotBlank @field:Size(max = 253) @field:Pattern(regexp = "^[A-Za-z0-9.-]+$") val hostname: String,
    @field:NotBlank @field:Size(max = 40) val runtimeVersion: String,
)
data class EnrollVoiceSatelliteResponse(val satelliteId: UUID, val satelliteToken: String)
data class OpenVoiceSessionResponse(val sessionId: UUID, val conversationId: UUID, val expiresAt: Instant)
data class CloseVoiceSessionRequest(
    val sessionId: UUID,
    @field:Pattern(regexp = "^(explicit|inactivity|maximum|error|interrupted)$") val reason: String,
)

@RestController
@RequestMapping("/v1/voice-satellites")
class VoiceSatelliteOwnerController(private val service: VoiceSatelliteService) {
    @PostMapping("/enrollments")
    @ResponseStatus(HttpStatus.CREATED)
    fun createEnrollment(
        @Valid @RequestBody body: CreateVoiceEnrollmentRequest,
        request: HttpServletRequest,
    ): VoiceEnrollmentResponse {
        val ownerId = request.getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID
            ?: throw VoiceSatelliteUnauthenticatedException()
        val created = service.createEnrollment(ownerId, body.displayName.trim())
        return VoiceEnrollmentResponse(created.id, created.token, created.expiresAt)
    }
}

@RestController
@RequestMapping("/v1/voice-satellite")
class VoiceSatelliteAgentController(private val service: VoiceSatelliteService) {
    @PostMapping("/enroll")
    @ResponseStatus(HttpStatus.CREATED)
    fun enroll(@Valid @RequestBody body: EnrollVoiceSatelliteRequest): EnrollVoiceSatelliteResponse {
        val registered = service.enroll(
            body.enrollmentToken, body.hostname.lowercase(), body.runtimeVersion,
        )
        return EnrollVoiceSatelliteResponse(registered.satellite.id, registered.token)
    }

    @PostMapping("/sessions")
    @ResponseStatus(HttpStatus.CREATED)
    fun openSession(
        @RequestHeader("X-Kyrion-Satellite-Id") satelliteId: UUID,
        @RequestHeader("Authorization") authorization: String,
    ): OpenVoiceSessionResponse {
        val session = service.openSession(satelliteId, authorization.bearer())
        return OpenVoiceSessionResponse(session.id, session.conversationId, session.expiresAt)
    }

    @PostMapping("/sessions/close")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun closeSession(
        @RequestHeader("X-Kyrion-Satellite-Id") satelliteId: UUID,
        @RequestHeader("Authorization") authorization: String,
        @Valid @RequestBody body: CloseVoiceSessionRequest,
    ) = service.closeSession(satelliteId, authorization.bearer(), body.sessionId, body.reason)

    private fun String.bearer(): String =
        takeIf { startsWith("Bearer ") && length > 7 }?.substring(7)
            ?: throw VoiceSatelliteUnauthenticatedException()
}

@RestControllerAdvice
class VoiceSatelliteErrorHandler {
    @ExceptionHandler(VoiceSatelliteUnauthenticatedException::class)
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    fun unauthenticated() = mapOf("code" to "VOICE_SATELLITE_UNAUTHENTICATED")

    @ExceptionHandler(VoiceSessionNotFoundException::class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    fun sessionNotFound() = mapOf("code" to "VOICE_SESSION_NOT_FOUND")

    @ExceptionHandler(VoiceSessionInactiveException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun sessionInactive() = mapOf("code" to "VOICE_SESSION_INACTIVE")

    @ExceptionHandler(VoiceAudioInvalidException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun audioInvalid() = mapOf("code" to "VOICE_AUDIO_INVALID")

    @ExceptionHandler(VoiceSpeechUnavailableException::class)
    @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)
    fun speechUnavailable() = mapOf("code" to "VOICE_SPEECH_UNAVAILABLE")
}

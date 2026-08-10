package dev.kyrion.core.voice

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestHeader
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.slf4j.LoggerFactory
import java.io.BufferedReader
import java.time.Clock
import java.util.Base64
import java.util.UUID

private const val PCM_SAMPLE_RATE = 16_000
private const val PCM_CHANNELS = 1
private const val PCM_SAMPLE_BYTES = 2
private const val MAX_FRAME_MILLISECONDS = 100
private const val MAX_TURN_SECONDS = 60
private const val MAX_EVENT_BYTES = 8_192
private const val MAX_FRAMES = MAX_TURN_SECONDS * 1_000 / 20
private const val MAX_PCM_BYTES = PCM_SAMPLE_RATE * PCM_CHANNELS * PCM_SAMPLE_BYTES * MAX_TURN_SECONDS

data class VoicePcmIngressEvent(
    val type: String = "",
    val sessionId: UUID? = null,
    val turnId: UUID? = null,
    val sampleRate: Int? = null,
    val channels: Int? = null,
    val sequence: Long? = null,
    val capturedAtEpochMillis: Long? = null,
    val audioBase64: String? = null,
    val reason: String? = null,
)

data class VoicePcmIngressResult(
    val sessionId: UUID,
    val turnId: UUID,
    val status: String,
    val framesReceived: Int,
    val pcmBytesReceived: Long,
    val firstSequence: Long?,
    val lastSequence: Long?,
    val firstFrameLatencyMillis: Long?,
    val maximumFrameLatencyMillis: Long?,
)

@Service
class VoicePcmIngressService(
    private val satellites: VoiceSatelliteService,
    private val clock: Clock = Clock.systemUTC(),
) {
    private val mapper: ObjectMapper = jacksonObjectMapper()
    fun receive(
        satelliteId: UUID,
        credential: String,
        sessionId: UUID,
        turnId: UUID,
        reader: BufferedReader,
    ): VoicePcmIngressResult {
        satellites.activeSession(satelliteId, credential, sessionId)
        var started = false
        var terminal = false
        var expectedSequence = 0L
        var frames = 0
        var pcmBytes = 0L
        var firstLatency: Long? = null
        var maximumLatency: Long? = null
        var status = "completed"

        while (true) {
            val line = readBoundedLine(reader) ?: break
            if (line.isBlank()) continue
            if (line.length > MAX_EVENT_BYTES) throw VoicePcmIngressInvalidException("EVENT_TOO_LARGE")
            val event = try {
                mapper.readValue(line, VoicePcmIngressEvent::class.java)
            } catch (_: Exception) {
                throw VoicePcmIngressInvalidException("INVALID_EVENT")
            }
            if (event.sessionId != sessionId || event.turnId != turnId) {
                throw VoicePcmIngressInvalidException("SCOPE_MISMATCH")
            }
            when (event.type) {
                "start" -> {
                    if (started || terminal || event.sampleRate != PCM_SAMPLE_RATE || event.channels != PCM_CHANNELS) {
                        throw VoicePcmIngressInvalidException("INVALID_START")
                    }
                    started = true
                }
                "audio" -> {
                    if (!started || terminal) throw VoicePcmIngressInvalidException("INVALID_STATE")
                    val sequence = event.sequence ?: throw VoicePcmIngressInvalidException("MISSING_SEQUENCE")
                    if (sequence != expectedSequence) throw VoicePcmSequenceException(expectedSequence, sequence)
                    if (frames >= MAX_FRAMES) throw VoicePcmIngressLimitException()
                    val pcm = try {
                        Base64.getDecoder().decode(event.audioBase64 ?: "")
                    } catch (_: IllegalArgumentException) {
                        throw VoicePcmIngressInvalidException("INVALID_AUDIO")
                    }
                    validateFrame(pcm, event.sampleRate, event.channels)
                    if (pcmBytes + pcm.size > MAX_PCM_BYTES) throw VoicePcmIngressLimitException()
                    val capturedAt = event.capturedAtEpochMillis
                        ?: throw VoicePcmIngressInvalidException("MISSING_TIMESTAMP")
                    val latency = (clock.millis() - capturedAt).coerceAtLeast(0)
                    firstLatency = firstLatency ?: latency
                    maximumLatency = maxOf(maximumLatency ?: latency, latency)
                    expectedSequence++
                    frames++
                    pcmBytes += pcm.size
                }
                "complete", "cancel" -> {
                    if (!started || terminal) throw VoicePcmIngressInvalidException("INVALID_STATE")
                    terminal = true
                    status = if (event.type == "cancel") "cancelled" else "completed"
                }
                else -> throw VoicePcmIngressInvalidException("UNKNOWN_EVENT")
            }
            if (terminal) break
        }
        if (!started) throw VoicePcmIngressInvalidException("START_REQUIRED")
        if (!terminal) throw VoicePcmDisconnectedException()
        LOGGER.info(
            "[VOICE] turn={} event=pcm_uplink_{} frames={} bytes={} first_latency_ms={} max_latency_ms={}",
            turnId, status, frames, pcmBytes, firstLatency, maximumLatency,
        )
        return VoicePcmIngressResult(
            sessionId, turnId, status, frames, pcmBytes,
            if (frames == 0) null else 0, if (frames == 0) null else expectedSequence - 1,
            firstLatency, maximumLatency,
        )
    }

    private fun readBoundedLine(reader: BufferedReader): String? {
        val line = StringBuilder()
        while (true) {
            val value = reader.read()
            if (value == -1) return line.takeIf { it.isNotEmpty() }?.toString()
            if (value.toChar() == '\n') return line.toString().trimEnd('\r')
            if (line.length >= MAX_EVENT_BYTES) throw VoicePcmIngressInvalidException("EVENT_TOO_LARGE")
            line.append(value.toChar())
        }
    }

    private fun validateFrame(pcm: ByteArray, sampleRate: Int?, channels: Int?) {
        if (sampleRate != PCM_SAMPLE_RATE || channels != PCM_CHANNELS || pcm.isEmpty()) {
            throw VoicePcmIngressInvalidException("INVALID_FORMAT")
        }
        val sampleFrameBytes = channels * PCM_SAMPLE_BYTES
        val maximumBytes = sampleRate * sampleFrameBytes * MAX_FRAME_MILLISECONDS / 1_000
        if (pcm.size % sampleFrameBytes != 0 || pcm.size > maximumBytes) {
            throw VoicePcmIngressInvalidException("INVALID_FRAME_SIZE")
        }
    }

    companion object {
        private val LOGGER = LoggerFactory.getLogger(VoicePcmIngressService::class.java)
    }
}

@RestController
@RequestMapping("/v1/voice-satellite/sessions")
class VoicePcmIngressController(private val ingress: VoicePcmIngressService) {
    @PostMapping("/{sessionId}/pcm-uplink", consumes = ["application/x-ndjson"])
    fun receive(
        @PathVariable sessionId: UUID,
        @RequestHeader("X-Kyrion-Satellite-Id") satelliteId: UUID,
        @RequestHeader("X-Kyrion-Voice-Turn-Id") turnId: UUID,
        @RequestHeader("Authorization") authorization: String,
        request: HttpServletRequest,
    ): VoicePcmIngressResult = ingress.receive(
        satelliteId, authorization.bearerToken(), sessionId, turnId,
        request.inputStream.bufferedReader(Charsets.UTF_8),
    )

    private fun String.bearerToken(): String =
        takeIf { startsWith("Bearer ") && length > 7 }?.substring(7)
            ?: throw VoiceSatelliteUnauthenticatedException()
}

class VoicePcmIngressInvalidException(val errorCode: String) : RuntimeException()
class VoicePcmSequenceException(val expected: Long, val received: Long) : RuntimeException()
class VoicePcmIngressLimitException : RuntimeException()
class VoicePcmDisconnectedException : RuntimeException()

data class VoicePcmErrorResponse(
    val code: String,
    val expectedSequence: Long? = null,
    val receivedSequence: Long? = null,
)

@org.springframework.web.bind.annotation.RestControllerAdvice
class VoicePcmIngressErrorHandler {
    @ExceptionHandler(VoicePcmIngressInvalidException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid(error: VoicePcmIngressInvalidException) = VoicePcmErrorResponse(error.errorCode)

    @ExceptionHandler(VoicePcmSequenceException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun sequence(error: VoicePcmSequenceException) = VoicePcmErrorResponse(
        "VOICE_PCM_SEQUENCE_INVALID", error.expected, error.received,
    )

    @ExceptionHandler(VoicePcmIngressLimitException::class)
    @ResponseStatus(HttpStatus.CONTENT_TOO_LARGE)
    fun limit() = VoicePcmErrorResponse("VOICE_PCM_LIMIT_EXCEEDED")

    @ExceptionHandler(VoicePcmDisconnectedException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun disconnected() = VoicePcmErrorResponse("VOICE_PCM_DISCONNECTED")
}

package dev.kyrion.core.voice

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import jakarta.validation.Valid
import jakarta.validation.constraints.Max
import jakarta.validation.constraints.Min
import jakarta.validation.constraints.Pattern
import org.slf4j.LoggerFactory
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestHeader
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody
import java.time.Clock
import java.util.Base64
import java.util.UUID
import kotlin.math.roundToInt
import kotlin.math.sin

private const val DOWNLINK_SAMPLE_RATE = 24_000
private const val DOWNLINK_CHANNELS = 1
private const val DOWNLINK_SAMPLE_BYTES = 2
private const val DOWNLINK_FRAME_MILLISECONDS = 160
private const val DOWNLINK_FRAME_BYTES =
    DOWNLINK_SAMPLE_RATE * DOWNLINK_CHANNELS * DOWNLINK_SAMPLE_BYTES * DOWNLINK_FRAME_MILLISECONDS / 1_000
private const val MAX_DOWNLINK_MILLISECONDS = 20_000

data class VoicePcmDownlinkRequest(
    val turnId: UUID,
    @field:Min(160) @field:Max(20_000)
    val durationMilliseconds: Int,
    @field:Pattern(regexp = "^(silence|tone)$")
    val signal: String = "silence",
)

data class VoicePcmDownlinkEvent(
    val type: String,
    val sessionId: UUID,
    val turnId: UUID,
    val sampleRate: Int? = null,
    val channels: Int? = null,
    val frameMilliseconds: Int? = null,
    val sequence: Long? = null,
    val producedAtEpochMillis: Long? = null,
    val audioBase64: String? = null,
    val framesSent: Int? = null,
    val pcmBytesSent: Long? = null,
)

@org.springframework.stereotype.Service
class VoicePcmDownlinkService(
    private val satellites: VoiceSatelliteService,
    private val clock: Clock = Clock.systemUTC(),
) {
    internal var monotonicNanos: () -> Long = System::nanoTime
    internal var paceUntil: (Long) -> Unit = { deadline ->
        val remaining = deadline - System.nanoTime()
        if (remaining > 0) {
            Thread.sleep(remaining / 1_000_000, (remaining % 1_000_000).toInt())
        }
    }

    fun validate(
        satelliteId: UUID,
        credential: String,
        sessionId: UUID,
        request: VoicePcmDownlinkRequest,
    ) {
        satellites.activeSession(satelliteId, credential, sessionId)
        if (request.durationMilliseconds % DOWNLINK_FRAME_MILLISECONDS != 0) {
            throw VoicePcmDownlinkInvalidException("INVALID_DURATION")
        }
    }

    fun streamSynthetic(
        satelliteId: UUID,
        credential: String,
        sessionId: UUID,
        request: VoicePcmDownlinkRequest,
        emit: (VoicePcmDownlinkEvent) -> Unit,
    ) {
        validate(satelliteId, credential, sessionId, request)
        val frameCount = request.durationMilliseconds / DOWNLINK_FRAME_MILLISECONDS
        val streamStartedAt = monotonicNanos()
        emit(
            VoicePcmDownlinkEvent(
                "start", sessionId, request.turnId, DOWNLINK_SAMPLE_RATE,
                DOWNLINK_CHANNELS, DOWNLINK_FRAME_MILLISECONDS,
            ),
        )
        repeat(frameCount) { sequence ->
            if (sequence > 0) {
                paceUntil(
                    streamStartedAt + sequence * DOWNLINK_FRAME_MILLISECONDS * 1_000_000L,
                )
            }
            val frame = syntheticFrame(sequence, request.signal)
            emit(
                VoicePcmDownlinkEvent(
                    type = "audio",
                    sessionId = sessionId,
                    turnId = request.turnId,
                    sampleRate = DOWNLINK_SAMPLE_RATE,
                    channels = DOWNLINK_CHANNELS,
                    sequence = sequence.toLong(),
                    producedAtEpochMillis = clock.millis(),
                    audioBase64 = Base64.getEncoder().encodeToString(frame),
                ),
            )
        }
        emit(
            VoicePcmDownlinkEvent(
                type = "complete",
                sessionId = sessionId,
                turnId = request.turnId,
                framesSent = frameCount,
                pcmBytesSent = frameCount.toLong() * DOWNLINK_FRAME_BYTES,
            ),
        )
        LOGGER.info(
            "[VOICE] turn={} event=pcm_downlink_completed frames={} bytes={}",
            request.turnId, frameCount, frameCount.toLong() * DOWNLINK_FRAME_BYTES,
        )
    }

    private fun syntheticFrame(sequence: Int, signal: String): ByteArray {
        val frame = ByteArray(DOWNLINK_FRAME_BYTES)
        if (signal == "silence") return frame
        val samplesPerFrame = DOWNLINK_FRAME_BYTES / DOWNLINK_SAMPLE_BYTES
        repeat(samplesPerFrame) { sample ->
            val absoluteSample = sequence.toLong() * samplesPerFrame + sample
            val value = (
                sin(2.0 * Math.PI * 440.0 * absoluteSample / DOWNLINK_SAMPLE_RATE) * 2_621.0
            ).roundToInt().toShort().toInt()
            frame[sample * 2] = (value and 0xff).toByte()
            frame[sample * 2 + 1] = ((value ushr 8) and 0xff).toByte()
        }
        return frame
    }

    companion object {
        private val LOGGER = LoggerFactory.getLogger(VoicePcmDownlinkService::class.java)
    }
}

@RestController
@RequestMapping("/v1/voice-satellite/sessions")
class VoicePcmDownlinkController(private val downlink: VoicePcmDownlinkService) {
    private val mapper: ObjectMapper = jacksonObjectMapper()

    @PostMapping(
        "/{sessionId}/pcm-downlink-prototype",
        consumes = ["application/json"],
        produces = ["application/x-ndjson"],
    )
    @ResponseStatus(HttpStatus.OK)
    fun stream(
        @PathVariable sessionId: UUID,
        @RequestHeader("X-Kyrion-Satellite-Id") satelliteId: UUID,
        @RequestHeader("Authorization") authorization: String,
        @Valid @RequestBody request: VoicePcmDownlinkRequest,
    ): StreamingResponseBody {
        val credential = authorization.takeIf { it.startsWith("Bearer ") }?.substring(7)
            ?: throw VoiceSatelliteUnauthenticatedException()
        downlink.validate(satelliteId, credential, sessionId, request)
        return StreamingResponseBody { output ->
            downlink.streamSynthetic(satelliteId, credential, sessionId, request) { event ->
                output.write(mapper.writeValueAsBytes(event))
                output.write('\n'.code)
                output.flush()
            }
        }
    }
}

class VoicePcmDownlinkInvalidException(val errorCode: String) : RuntimeException()

@org.springframework.web.bind.annotation.RestControllerAdvice
class VoicePcmDownlinkErrorHandler {
    @org.springframework.web.bind.annotation.ExceptionHandler(VoicePcmDownlinkInvalidException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid(error: VoicePcmDownlinkInvalidException) = mapOf("code" to error.errorCode)
}

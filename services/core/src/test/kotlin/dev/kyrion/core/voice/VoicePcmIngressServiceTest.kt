package dev.kyrion.core.voice

import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import org.mockito.Mockito.mock
import org.mockito.Mockito.`when`
import java.io.StringReader
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.Base64
import java.util.UUID

class VoicePcmIngressServiceTest {
    private val now = Instant.parse("2026-08-10T12:00:00Z")
    private val clock = Clock.fixed(now, ZoneOffset.UTC)
    private val satellites = mock(VoiceSatelliteService::class.java)
    private val service = VoicePcmIngressService(satellites, clock)
    private val satelliteId = UUID.randomUUID()
    private val sessionId = UUID.randomUUID()
    private val turnId = UUID.randomUUID()

    init {
        `when`(satellites.activeSession(satelliteId, "secret", sessionId)).thenReturn(
            mock(VoiceDialogueSession::class.java),
        )
    }

    @Test
    fun `accepts ordered frames and records bounded timing`() {
        val result = receive(start(), audio(0, now.toEpochMilli() - 12), audio(1, now.toEpochMilli() - 20), end())

        assertThat(result.status).isEqualTo("completed")
        assertThat(result.framesReceived).isEqualTo(2)
        assertThat(result.pcmBytesReceived).isEqualTo(5_120)
        assertThat(result.firstFrameLatencyMillis).isEqualTo(12)
        assertThat(result.maximumFrameLatencyMillis).isEqualTo(20)
    }

    @Test
    fun `rejects a sequence gap`() {
        assertThatThrownBy { receive(start(), audio(1, now.toEpochMilli()), end()) }
            .isInstanceOf(VoicePcmSequenceException::class.java)
    }

    @Test
    fun `rejects a stream that disconnects without a terminal event`() {
        assertThatThrownBy { receive(start(), audio(0, now.toEpochMilli())) }
            .isInstanceOf(VoicePcmDisconnectedException::class.java)
    }

    @Test
    fun `rejects an oversized event without buffering the remainder`() {
        val oversized = "x".repeat(8_193)

        assertThatThrownBy {
            service.receive(satelliteId, "secret", sessionId, turnId, StringReader(oversized).buffered())
        }.isInstanceOf(VoicePcmIngressInvalidException::class.java)
            .extracting("errorCode").isEqualTo("EVENT_TOO_LARGE")
    }

    @Test
    fun `accepts explicit cancellation`() {
        val result = receive(start(), audio(0, now.toEpochMilli()), end("cancel"))

        assertThat(result.status).isEqualTo("cancelled")
        assertThat(result.framesReceived).isEqualTo(1)
    }

    @Test
    fun `a reconnect starts a new bounded request at sequence zero`() {
        val first = receive(start(), audio(0, now.toEpochMilli()), end())
        val second = receive(start(), audio(0, now.toEpochMilli()), end())

        assertThat(first.lastSequence).isEqualTo(0)
        assertThat(second.lastSequence).isEqualTo(0)
    }

    @Test
    fun `authentication failure is enforced before reading PCM`() {
        `when`(satellites.activeSession(satelliteId, "wrong", sessionId))
            .thenThrow(VoiceSatelliteUnauthenticatedException())

        assertThatThrownBy {
            service.receive(satelliteId, "wrong", sessionId, turnId, StringReader(start()).buffered())
        }.isInstanceOf(VoiceSatelliteUnauthenticatedException::class.java)
    }

    private fun receive(vararg events: String) = service.receive(
        satelliteId, "secret", sessionId, turnId, StringReader(events.joinToString("\n")).buffered(),
    )

    private fun start() = json("start", "\"sampleRate\":16000,\"channels\":1")

    private fun audio(sequence: Long, capturedAt: Long): String {
        val pcm = Base64.getEncoder().encodeToString(ByteArray(2_560))
        return json(
            "audio",
            "\"sampleRate\":16000,\"channels\":1,\"sequence\":$sequence," +
                "\"capturedAtEpochMillis\":$capturedAt,\"audioBase64\":\"$pcm\"",
        )
    }

    private fun end(type: String = "complete") = json(type, "")

    private fun json(type: String, fields: String): String {
        val suffix = if (fields.isEmpty()) "" else ",$fields"
        return "{\"type\":\"$type\",\"sessionId\":\"$sessionId\"," +
            "\"turnId\":\"$turnId\"$suffix}"
    }
}

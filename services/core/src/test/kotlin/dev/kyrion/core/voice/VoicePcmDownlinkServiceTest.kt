package dev.kyrion.core.voice

import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import org.mockito.Mockito.mock
import org.mockito.Mockito.verify
import org.mockito.Mockito.`when`
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.Base64
import java.util.UUID

class VoicePcmDownlinkServiceTest {
    private val now = Instant.parse("2026-08-10T15:00:00Z")
    private val satellites = mock(VoiceSatelliteService::class.java)
    private val service = VoicePcmDownlinkService(satellites, Clock.fixed(now, ZoneOffset.UTC)).apply {
        paceUntil = {}
    }
    private val satelliteId = UUID.randomUUID()
    private val sessionId = UUID.randomUUID()
    private val turnId = UUID.randomUUID()

    init {
        `when`(satellites.activeSession(satelliteId, "secret", sessionId)).thenReturn(
            mock(VoiceDialogueSession::class.java),
        )
    }

    @Test
    fun `streams scoped ordered bounded pcm events`() {
        val events = mutableListOf<VoicePcmDownlinkEvent>()

        service.streamSynthetic(
            satelliteId, "secret", sessionId, VoicePcmDownlinkRequest(turnId, 320), events::add,
        )

        assertThat(events.map { it.type }).containsExactly("start", "audio", "audio", "complete")
        assertThat(events.map { it.sessionId }).containsOnly(sessionId)
        assertThat(events.map { it.turnId }).containsOnly(turnId)
        assertThat(events.filter { it.type == "audio" }.map { it.sequence }).containsExactly(0L, 1L)
        assertThat(Base64.getDecoder().decode(events[1].audioBase64)).hasSize(7_680)
        assertThat(events.last().framesSent).isEqualTo(2)
        assertThat(events.last().pcmBytesSent).isEqualTo(15_360)
        verify(satellites).activeSession(satelliteId, "secret", sessionId)
    }

    @Test
    fun `paces against absolute deadlines without accumulating emission overhead`() {
        val deadlines = mutableListOf<Long>()
        val paced = VoicePcmDownlinkService(satellites, Clock.fixed(now, ZoneOffset.UTC)).apply {
            monotonicNanos = { 1_000_000_000L }
            paceUntil = deadlines::add
        }

        paced.streamSynthetic(
            satelliteId, "secret", sessionId, VoicePcmDownlinkRequest(turnId, 480), { _ -> },
        )

        assertThat(deadlines).containsExactly(1_160_000_000L, 1_320_000_000L)
    }

    @Test
    fun `generates a deterministic non-silent acceptance tone only when requested`() {
        val events = mutableListOf<VoicePcmDownlinkEvent>()

        service.streamSynthetic(
            satelliteId, "secret", sessionId,
            VoicePcmDownlinkRequest(turnId, 160, signal = "tone"), events::add,
        )

        assertThat(Base64.getDecoder().decode(events[1].audioBase64).any { it.toInt() != 0 }).isTrue()
    }

    @Test
    fun `rejects a duration that is not a complete frame`() {
        assertThatThrownBy {
            service.streamSynthetic(
                satelliteId, "secret", sessionId, VoicePcmDownlinkRequest(turnId, 100), { _ -> },
            )
        }.isInstanceOf(VoicePcmDownlinkInvalidException::class.java)
            .extracting("errorCode").isEqualTo("INVALID_DURATION")
    }

    @Test
    fun `authenticates before emitting audio`() {
        `when`(satellites.activeSession(satelliteId, "wrong", sessionId))
            .thenThrow(VoiceSatelliteUnauthenticatedException())
        val events = mutableListOf<VoicePcmDownlinkEvent>()

        assertThatThrownBy {
            service.streamSynthetic(
                satelliteId, "wrong", sessionId, VoicePcmDownlinkRequest(turnId, 160), events::add,
            )
        }.isInstanceOf(VoiceSatelliteUnauthenticatedException::class.java)
        assertThat(events).isEmpty()
    }
}

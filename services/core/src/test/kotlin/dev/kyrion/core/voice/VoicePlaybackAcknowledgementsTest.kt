package dev.kyrion.core.voice

import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class VoicePlaybackAcknowledgementsTest {
    @Test
    fun `execution barrier opens only after playback acknowledgement`() {
        val acknowledgements = VoicePlaybackAcknowledgements()
        acknowledgements.expect("turn")
        val executor = Executors.newSingleThreadExecutor()
        try {
            val waiting = executor.submit { acknowledgements.await("turn") }

            Thread.sleep(50)
            assert(!waiting.isDone)
            acknowledgements.acknowledge("turn")

            waiting.get(1, TimeUnit.SECONDS)
        } finally {
            executor.shutdownNow()
        }
    }

    @Test
    fun `rejects acknowledgements for an unknown turn`() {
        assertThatThrownBy { VoicePlaybackAcknowledgements().acknowledge("unknown") }
            .isInstanceOf(VoicePlaybackAcknowledgementInvalidException::class.java)
    }
}

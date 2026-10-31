package dev.kyrion.core.voice

import com.sun.net.httpserver.HttpServer
import dev.kyrion.core.ai.AiOrchestrationService
import dev.kyrion.core.conversation.ConversationRepository
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import java.net.InetSocketAddress
import java.time.Clock
import java.util.UUID
import java.util.concurrent.atomic.AtomicInteger

class VoiceNoSpeechTest {
    @Test
    fun `empty recognition closes authenticated session without model actions persistence or audio`() {
        val requests = AtomicInteger()
        val server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
        server.createContext("/v1/speech/transcribe") { exchange ->
            exchange.requestBody.readAllBytes()
            requests.incrementAndGet()
            val body = """{"text":"  \n ","locale":"de"}""".toByteArray()
            exchange.responseHeaders.add("Content-Type", "application/json")
            exchange.sendResponseHeaders(200, body.size.toLong())
            exchange.responseBody.use { it.write(body) }
        }
        server.start()
        try {
            val satellites = mock(VoiceSatelliteService::class.java)
            val conversations = mock(ConversationRepository::class.java)
            val policies = mock(VoiceResponsePolicyRegistry::class.java)
            val actions = mock(VoiceActionService::class.java)
            val models = mock(AiOrchestrationService::class.java)
            val satellite = UUID.randomUUID()
            val session = UUID.randomUUID()
            `when`(satellites.activeSession(satellite, "credential", session))
                .thenReturn(mock(VoiceDialogueSession::class.java))
            val service = VoiceDialogueService(
                satellites, conversations, policies, actions,
                VoicePlaybackAcknowledgements(), PendingVoiceActions(),
                "http://127.0.0.1:${server.address.port}", Clock.systemUTC(), models,
            )
            val events = mutableListOf<VoiceTurnEvent>()
            val wav = ByteArray(44).also { "RIFF".toByteArray().copyInto(it) }
            service.streamTurn(satellite, "credential", session, "de", wav, UUID.randomUUID().toString(), events::add)
            verify(satellites).activeSession(satellite, "credential", session)
            verify(satellites).closeSession(satellite, "credential", session, "inactivity")
            verifyNoMoreInteractions(satellites)
            verifyNoInteractions(conversations, policies, actions, models)
            assertThat(requests.get()).isEqualTo(1)
            assertThat(events.last()).isEqualTo(
                VoiceTurnEvent(type = "completed", outcome = "no_speech", continueSession = false),
            )
            assertThat(events.count { it.type == "completed" }).isEqualTo(1)
            assertThat(events.none { it.type in listOf("transcript", "audio.chunk", "answer.started") }).isTrue()
        } finally {
            server.stop(0)
        }
    }
}

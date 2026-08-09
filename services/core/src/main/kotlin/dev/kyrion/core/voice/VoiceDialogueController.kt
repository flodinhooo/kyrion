package dev.kyrion.core.voice

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.conversation.ConversationMessage
import dev.kyrion.core.conversation.ConversationRepository
import dev.kyrion.core.conversation.ConversationTurnStatus
import jakarta.validation.constraints.Pattern
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.HttpStatus
import org.springframework.http.HttpEntity
import org.springframework.http.HttpHeaders
import org.springframework.http.MediaType
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestHeader
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.client.RestTemplate
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody
import java.time.Clock
import java.util.Base64
import java.util.UUID

data class VoiceTurnEvent(
    val type: String,
    val transcript: String? = null,
    val responseText: String? = null,
    val audioBase64: String? = null,
    val continueSession: Boolean? = null,
)

data class AiTranscriptionResponse(val text: String, val locale: String)

@Service
class VoiceDialogueService(
    private val satellites: VoiceSatelliteService,
    private val conversations: ConversationRepository,
    @Value("\${kyrion.ai.url:http://127.0.0.1:8000}") aiUrl: String,
    private val clock: Clock = Clock.systemUTC(),
) {
    private val aiBaseUrl = aiUrl.trimEnd('/')
    private val ai = RestTemplate()
    private val objectMapper: ObjectMapper = jacksonObjectMapper()

    fun streamTurn(
        satelliteId: UUID,
        credential: String,
        sessionId: UUID,
        locale: String,
        audio: ByteArray,
        emit: (VoiceTurnEvent) -> Unit,
    ) {
        if (audio.size !in 44..1_000_000 || !audio.copyOfRange(0, 4).contentEquals("RIFF".toByteArray())) {
            throw VoiceAudioInvalidException()
        }
        val session = satellites.activeSession(satelliteId, credential, sessionId)
        val headers = HttpHeaders().apply {
            contentType = MediaType.parseMediaType("audio/wav")
            contentLength = audio.size.toLong()
            set("X-Kyrion-Locale", locale)
        }
        val transcript = ai.postForEntity(
            "$aiBaseUrl/v1/speech/transcribe",
            HttpEntity(audio, headers),
            AiTranscriptionResponse::class.java,
        ).body?.text?.trim().orEmpty()
        if (transcript.isBlank()) throw VoiceAudioInvalidException()
        emit(VoiceTurnEvent(type = "transcript", transcript = transcript))

        val explicitEnd = normalized(transcript) in STOP_PHRASES
        val now = clock.instant()
        val userMessage = ConversationMessage(UUID.randomUUID(), "user", transcript, now)
        val conversation = conversations.startTurn(
            session.ownerId, session.conversationId, "Voice conversation", userMessage, now,
        )
        val responseText = if (explicitEnd) {
            if (locale == "de") "Bis später." else "Talk to you later."
        } else {
            chatAndSpeak(session.conversationId, locale, conversation.messages.takeLast(12), emit)
        }
        if (explicitEnd) emitAudio(responseText, locale, emit)
        conversations.finishTurn(
            session.ownerId, session.conversationId, userMessage.id,
            ConversationMessage(UUID.randomUUID(), "assistant", responseText, clock.instant()),
            ConversationTurnStatus.completed, null, clock.instant(),
        )
        if (explicitEnd) satellites.closeSession(satelliteId, credential, sessionId, "explicit")
        emit(VoiceTurnEvent(type = "completed", responseText = responseText, continueSession = !explicitEnd))
    }

    private fun chatAndSpeak(
        conversationId: UUID,
        locale: String,
        messages: List<ConversationMessage>,
        emit: (VoiceTurnEvent) -> Unit,
    ): String {
        val body = mapOf(
            "conversationId" to conversationId.toString(),
            "locale" to locale,
            "messages" to messages.map { mapOf("role" to it.role, "content" to it.content) },
            "memoryContext" to emptyList<Any>(),
        )
        val response = StringBuilder()
        val pendingSpeech = StringBuilder()
        var sentenceCount = 0
        ai.execute(
            "$aiBaseUrl/v1/chat/stream",
            org.springframework.http.HttpMethod.POST,
            { request ->
                request.headers.contentType = MediaType.APPLICATION_JSON
                objectMapper.writeValue(request.body, body)
            },
            { result ->
                result.body.bufferedReader().useLines { lines ->
                    lines.filter { it.isNotBlank() }.forEach { line ->
                        val event = objectMapper.readTree(line)
                        if (event.path("type").asText() == "error") throw VoiceSpeechUnavailableException()
                        if (event.path("type").asText() == "message.delta") {
                            val delta = event.path("delta").asText()
                            response.append(delta)
                            pendingSpeech.append(delta)
                            sentenceCount += delta.count { it == '.' || it == '!' || it == '?' }
                            if (sentenceCount >= SENTENCES_PER_CHUNK) {
                                emitAudio(pendingSpeech.toString().trim(), locale, emit)
                                pendingSpeech.clear()
                                sentenceCount = 0
                            }
                        }
                    }
                }
            },
        )
        pendingSpeech.toString().trim().takeIf { it.isNotEmpty() }?.let { emitAudio(it, locale, emit) }
        return response.toString().trim().takeIf { it.isNotEmpty() }
            ?: throw VoiceSpeechUnavailableException()
    }

    private fun normalized(value: String) = value.lowercase().trim().replace(Regex("[.!?]+$"), "")

    private fun emitAudio(text: String, locale: String, emit: (VoiceTurnEvent) -> Unit) {
        val audio = ai.postForEntity(
            "$aiBaseUrl/v1/speech/synthesize",
            HttpEntity(
                mapOf("text" to text, "locale" to locale),
                HttpHeaders().apply { contentType = MediaType.APPLICATION_JSON },
            ),
            ByteArray::class.java,
        ).body ?: throw VoiceSpeechUnavailableException()
        emit(VoiceTurnEvent(type = "audio.chunk", audioBase64 = Base64.getEncoder().encodeToString(audio)))
    }

    companion object {
        private const val SENTENCES_PER_CHUNK = 2
        private val STOP_PHRASES = setOf(
            "stopp", "abbrechen", "danke", "bis später", "tschüss",
            "stop", "cancel", "thanks", "thank you", "goodbye",
        )
    }
}

@RestController
@RequestMapping("/v1/voice-satellite/sessions")
class VoiceDialogueController(private val dialogue: VoiceDialogueService) {
    @PostMapping("/{sessionId}/turns", consumes = ["audio/wav"], produces = ["application/x-ndjson"])
    @ResponseStatus(HttpStatus.OK)
    fun turn(
        @PathVariable sessionId: UUID,
        @RequestHeader("X-Kyrion-Satellite-Id") satelliteId: UUID,
        @RequestHeader("Authorization") authorization: String,
        @RequestHeader("X-Kyrion-Locale", defaultValue = "de")
        @Pattern(regexp = "^(de|en)$") locale: String,
        @RequestBody audio: ByteArray,
    ): StreamingResponseBody {
        val credential = authorization.takeIf { it.startsWith("Bearer ") }?.substring(7)
            ?: throw VoiceSatelliteUnauthenticatedException()
        return StreamingResponseBody { output ->
            dialogue.streamTurn(satelliteId, credential, sessionId, locale, audio) { event ->
                objectMapper.writeValue(output, event)
                output.write('\n'.code)
                output.flush()
            }
        }
    }

    private val objectMapper: ObjectMapper = jacksonObjectMapper()
}

class VoiceAudioInvalidException : RuntimeException()
class VoiceSpeechUnavailableException : RuntimeException()

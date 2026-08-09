package dev.kyrion.core.voice

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.conversation.ConversationMessage
import dev.kyrion.core.conversation.ConversationRepository
import dev.kyrion.core.conversation.ConversationTurnStatus
import jakarta.validation.constraints.Pattern
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.HttpStatus
import org.springframework.http.MediaType
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestHeader
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.client.RestClient
import java.time.Clock
import java.util.Base64
import java.util.UUID

data class VoiceTurnResponse(
    val transcript: String,
    val responseText: String,
    val audioBase64: String,
    val continueSession: Boolean,
)

data class AiTranscriptionResponse(val text: String, val locale: String)

@Service
class VoiceDialogueService(
    private val satellites: VoiceSatelliteService,
    private val conversations: ConversationRepository,
    @Value("\${kyrion.ai.url:http://127.0.0.1:8000}") aiUrl: String,
    private val clock: Clock = Clock.systemUTC(),
) {
    private val ai = RestClient.create(aiUrl)
    private val objectMapper: ObjectMapper = jacksonObjectMapper()

    fun turn(
        satelliteId: UUID,
        credential: String,
        sessionId: UUID,
        locale: String,
        audio: ByteArray,
    ): VoiceTurnResponse {
        if (audio.size !in 44..1_000_000 || !audio.copyOfRange(0, 4).contentEquals("RIFF".toByteArray())) {
            throw VoiceAudioInvalidException()
        }
        val session = satellites.activeSession(satelliteId, credential, sessionId)
        val transcript = ai.post().uri("/v1/speech/transcribe")
            .contentType(MediaType.parseMediaType("audio/wav"))
            .header("X-Kyrion-Locale", locale)
            .body { outputStream -> outputStream.write(audio) }
            .retrieve()
            .body(AiTranscriptionResponse::class.java)?.text?.trim().orEmpty()
        if (transcript.isBlank()) throw VoiceAudioInvalidException()

        val explicitEnd = normalized(transcript) in STOP_PHRASES
        val now = clock.instant()
        val userMessage = ConversationMessage(UUID.randomUUID(), "user", transcript, now)
        val conversation = conversations.startTurn(
            session.ownerId, session.conversationId, "Voice conversation", userMessage, now,
        )
        val responseText = if (explicitEnd) {
            if (locale == "de") "Bis später." else "Talk to you later."
        } else {
            chat(session.conversationId, locale, conversation.messages.takeLast(12))
        }
        conversations.finishTurn(
            session.ownerId, session.conversationId, userMessage.id,
            ConversationMessage(UUID.randomUUID(), "assistant", responseText, clock.instant()),
            ConversationTurnStatus.completed, null, clock.instant(),
        )
        val synthesized = ai.post().uri("/v1/speech/synthesize")
            .contentType(MediaType.APPLICATION_JSON)
            .body(mapOf("text" to responseText, "locale" to locale)).retrieve().body(ByteArray::class.java)
            ?: throw VoiceSpeechUnavailableException()
        if (explicitEnd) satellites.closeSession(satelliteId, credential, sessionId, "explicit")
        return VoiceTurnResponse(
            transcript, responseText, Base64.getEncoder().encodeToString(synthesized), !explicitEnd,
        )
    }

    private fun chat(
        conversationId: UUID,
        locale: String,
        messages: List<ConversationMessage>,
    ): String {
        val body = mapOf(
            "conversationId" to conversationId.toString(),
            "locale" to locale,
            "messages" to messages.map { mapOf("role" to it.role, "content" to it.content) },
            "memoryContext" to emptyList<Any>(),
        )
        val ndjson = ai.post().uri("/v1/chat/stream").contentType(MediaType.APPLICATION_JSON)
            .body(body).retrieve().body(String::class.java).orEmpty()
        val response = StringBuilder()
        for (line in ndjson.lineSequence().filter { it.isNotBlank() }) {
            val event = objectMapper.readTree(line)
            if (event.path("type").asText() == "error") throw VoiceSpeechUnavailableException()
            if (event.path("type").asText() == "message.delta") response.append(event.path("delta").asText())
        }
        return response.toString().trim().takeIf { it.isNotEmpty() }
            ?: throw VoiceSpeechUnavailableException()
    }

    private fun normalized(value: String) = value.lowercase().trim().replace(Regex("[.!?]+$"), "")

    companion object {
        private val STOP_PHRASES = setOf(
            "stopp", "abbrechen", "danke", "bis später", "tschüss",
            "stop", "cancel", "thanks", "thank you", "goodbye",
        )
    }
}

@RestController
@RequestMapping("/v1/voice-satellite/sessions")
class VoiceDialogueController(private val dialogue: VoiceDialogueService) {
    @PostMapping("/{sessionId}/turns", consumes = ["audio/wav"])
    @ResponseStatus(HttpStatus.OK)
    fun turn(
        @PathVariable sessionId: UUID,
        @RequestHeader("X-Kyrion-Satellite-Id") satelliteId: UUID,
        @RequestHeader("Authorization") authorization: String,
        @RequestHeader("X-Kyrion-Locale", defaultValue = "de")
        @Pattern(regexp = "^(de|en)$") locale: String,
        @RequestBody audio: ByteArray,
    ): VoiceTurnResponse = dialogue.turn(
        satelliteId,
        authorization.takeIf { it.startsWith("Bearer ") }?.substring(7)
            ?: throw VoiceSatelliteUnauthenticatedException(),
        sessionId,
        locale,
        audio,
    )
}

class VoiceAudioInvalidException : RuntimeException()
class VoiceSpeechUnavailableException : RuntimeException()

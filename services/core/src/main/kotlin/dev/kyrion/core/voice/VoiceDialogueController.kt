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
import org.slf4j.LoggerFactory
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
import java.text.Normalizer
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
data class VoiceGreetingResponse(val responseText: String, val audioBase64: String)

@Service
class VoiceDialogueService(
    private val satellites: VoiceSatelliteService,
    private val conversations: ConversationRepository,
    private val responsePolicies: VoiceResponsePolicyRegistry,
    @Value("\${kyrion.ai.url:http://127.0.0.1:8000}") aiUrl: String,
    private val clock: Clock = Clock.systemUTC(),
) {
    private val aiBaseUrl = aiUrl.trimEnd('/')
    private val ai = RestTemplate()
    private val objectMapper: ObjectMapper = jacksonObjectMapper()

    fun greeting(
        satelliteId: UUID,
        credential: String,
        sessionId: UUID,
        locale: String,
    ): VoiceGreetingResponse {
        val session = satellites.activeSession(satelliteId, credential, sessionId)
        val greetingTurnId = UUID.nameUUIDFromBytes("voice-greeting:$sessionId".toByteArray())
        val plan = responsePolicies.resolve(
            SessionGreetingOutcome,
            VoiceResponseContext(session.ownerId, sessionId, greetingTurnId, locale),
        )
        val audio = resolveAudio(plan, greetingTurnId.toString())
        return VoiceGreetingResponse(
            responseText = plan.renderedText,
            audioBase64 = Base64.getEncoder().encodeToString(audio),
        )
    }

    fun streamTurn(
        satelliteId: UUID,
        credential: String,
        sessionId: UUID,
        locale: String,
        audio: ByteArray,
        turnId: String,
        emit: (VoiceTurnEvent) -> Unit,
    ) {
        if (audio.size !in 44..1_000_000 || !audio.copyOfRange(0, 4).contentEquals("RIFF".toByteArray())) {
            throw VoiceAudioInvalidException()
        }
        val session = satellites.activeSession(satelliteId, credential, sessionId)
        voiceEvent(turnId, "stt_start")
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
        voiceEvent(turnId, "stt_first_result")
        voiceEvent(turnId, "stt_complete")
        if (transcript.isBlank()) throw VoiceAudioInvalidException()
        emit(VoiceTurnEvent(type = "transcript", transcript = transcript))

        val explicitEnd = isVoiceSessionEnd(transcript)
        val now = clock.instant()
        val userMessage = ConversationMessage(UUID.randomUUID(), "user", transcript, now)
        val conversation = conversations.startTurn(
            session.ownerId, session.conversationId, "Voice conversation", userMessage, now,
        )
        if (!explicitEnd) {
            val acknowledgement = responsePolicies.resolve(
                DialogueAcknowledgedOutcome,
                VoiceResponseContext(
                    session.ownerId,
                    sessionId,
                    UUID.fromString(turnId),
                    locale,
                ),
            )
            emitAudio(acknowledgement, turnId, emit)
        }
        val outcome = if (explicitEnd) {
            SessionFarewellOutcome
        } else {
            DynamicDialogueOutcome(
                chat(session.conversationId, locale, conversation.messages.takeLast(12), turnId),
            )
        }
        val responsePlan = responsePolicies.resolve(
            outcome,
            VoiceResponseContext(
                session.ownerId,
                sessionId,
                UUID.fromString(turnId),
                locale,
            ),
        )
        emitAudio(responsePlan, turnId, emit)
        val responseText = responsePlan.renderedText
        conversations.finishTurn(
            session.ownerId, session.conversationId, userMessage.id,
            ConversationMessage(UUID.randomUUID(), "assistant", responseText, clock.instant()),
            ConversationTurnStatus.completed, null, clock.instant(),
        )
        if (explicitEnd) satellites.closeSession(satelliteId, credential, sessionId, "explicit")
        emit(VoiceTurnEvent(type = "completed", responseText = responseText, continueSession = !explicitEnd))
    }

    private fun chat(
        conversationId: UUID,
        locale: String,
        messages: List<ConversationMessage>,
        turnId: String,
    ): String {
        val body = mapOf(
            "conversationId" to conversationId.toString(),
            "locale" to locale,
            "messages" to messages.map { mapOf("role" to it.role, "content" to it.content) },
            "memoryContext" to emptyList<Any>(),
            "interactionMode" to "voice",
            "modelId" to "gemma3:1b",
            "voiceTurnId" to turnId,
        )
        val response = StringBuilder()
        var firstTokenSeen = false
        voiceEvent(turnId, "llm_request")
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
                            if (!firstTokenSeen) {
                                firstTokenSeen = true
                                voiceEvent(turnId, "llm_first_token")
                            }
                            val delta = event.path("delta").asText()
                            response.append(delta)
                        }
                    }
                }
            },
        )
        voiceEvent(turnId, "llm_complete")
        val complete = response.toString().trim().takeIf { it.isNotEmpty() }
            ?: throw VoiceSpeechUnavailableException()
        return complete
    }

    private fun emitAudio(
        plan: VoiceResponsePlan,
        turnId: String,
        emit: (VoiceTurnEvent) -> Unit,
    ) {
        val audio = resolveAudio(plan, turnId)
        emit(VoiceTurnEvent(type = "audio.chunk", audioBase64 = Base64.getEncoder().encodeToString(audio)))
        voiceEvent(turnId, "satellite_first_chunk_sent")
    }

    private fun resolveAudio(plan: VoiceResponsePlan, turnId: String): ByteArray {
        voiceEvent(turnId, "tts_request")
        val audio = ai.postForEntity(
            "$aiBaseUrl/v1/speech/resolve-response",
            HttpEntity(
                plan,
                HttpHeaders().apply { contentType = MediaType.APPLICATION_JSON },
            ),
            ByteArray::class.java,
        ).body ?: throw VoiceSpeechUnavailableException()
        if (
            audio.size !in 44..10_000_000 ||
            !audio.copyOfRange(0, 4).contentEquals("RIFF".toByteArray()) ||
            !audio.copyOfRange(8, 12).contentEquals("WAVE".toByteArray())
        ) {
            throw VoiceSpeechUnavailableException()
        }
        voiceEvent(turnId, "tts_first_audio")
        voiceEvent(turnId, "tts_complete")
        return audio
    }

    private fun voiceEvent(turnId: String, event: String) {
        LOGGER.info("[VOICE] turn={} event={} ts_ms={}", turnId, event, System.currentTimeMillis())
    }

    companion object {
        private val LOGGER = LoggerFactory.getLogger(VoiceDialogueService::class.java)
    }
}

private val SESSION_ENDINGS = listOf(
    listOf("bis", "spater"),
    listOf("bis", "spaeter"),
    listOf("tschuss"),
    listOf("auf", "wiedersehen"),
    listOf("das", "wars"),
    listOf("danke"),
    listOf("goodbye"),
    listOf("thanks"),
    listOf("thank", "you"),
    listOf("talk", "to", "you", "later"),
    listOf("thats", "all"),
    listOf("stop"),
    listOf("stopp"),
    listOf("cancel"),
    listOf("abbrechen"),
)

private val SESSION_END_PREFIX_WORDS = setOf(
    "ok", "okay", "passt", "gut", "danke", "dir", "vielen", "dank", "alles", "klar",
    "ja", "prima", "super", "bitte", "schon", "thanks", "thank", "you", "alright",
    "fine", "great", "done",
)

internal fun isVoiceSessionEnd(transcript: String): Boolean {
    val words = normalizedVoiceWords(transcript)
    if (words.isEmpty()) return false

    return SESSION_ENDINGS.any { ending ->
        if (words.size < ending.size || words.takeLast(ending.size) != ending) return@any false
        words.dropLast(ending.size).all(SESSION_END_PREFIX_WORDS::contains)
    }
}

private fun normalizedVoiceWords(value: String): List<String> = Normalizer
    .normalize(value.lowercase(), Normalizer.Form.NFKD)
    .replace(Regex("\\p{M}+"), "")
    .replace("'", "")
    .replace("’", "")
    .replace(Regex("[^a-z0-9]+"), " ")
    .trim()
    .split(Regex("\\s+"))
    .filter(String::isNotEmpty)

@RestController
@RequestMapping("/v1/voice-satellite/sessions")
class VoiceDialogueController(private val dialogue: VoiceDialogueService) {
    @PostMapping("/{sessionId}/greeting", produces = ["application/json"])
    fun greeting(
        @PathVariable sessionId: UUID,
        @RequestHeader("X-Kyrion-Satellite-Id") satelliteId: UUID,
        @RequestHeader("Authorization") authorization: String,
        @RequestHeader("X-Kyrion-Locale", defaultValue = "de")
        @Pattern(regexp = "^(de|en)$") locale: String,
    ): VoiceGreetingResponse {
        val credential = authorization.takeIf { it.startsWith("Bearer ") }?.substring(7)
            ?: throw VoiceSatelliteUnauthenticatedException()
        return dialogue.greeting(satelliteId, credential, sessionId, locale)
    }

    @PostMapping("/{sessionId}/turns", consumes = ["audio/wav"], produces = ["application/x-ndjson"])
    @ResponseStatus(HttpStatus.OK)
    fun turn(
        @PathVariable sessionId: UUID,
        @RequestHeader("X-Kyrion-Satellite-Id") satelliteId: UUID,
        @RequestHeader("Authorization") authorization: String,
        @RequestHeader("X-Kyrion-Locale", defaultValue = "de")
        @Pattern(regexp = "^(de|en)$") locale: String,
        @RequestHeader("X-Kyrion-Voice-Turn-Id") turnId: UUID,
        @RequestBody audio: ByteArray,
    ): StreamingResponseBody {
        val credential = authorization.takeIf { it.startsWith("Bearer ") }?.substring(7)
            ?: throw VoiceSatelliteUnauthenticatedException()
        return StreamingResponseBody { output ->
            dialogue.streamTurn(satelliteId, credential, sessionId, locale, audio, turnId.toString()) { event ->
                output.write(objectMapper.writeValueAsBytes(event))
                output.write('\n'.code)
                output.flush()
            }
        }
    }

    private val objectMapper: ObjectMapper = jacksonObjectMapper()
}

class VoiceAudioInvalidException : RuntimeException()
class VoiceSpeechUnavailableException : RuntimeException()

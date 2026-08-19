package dev.kyrion.core.action

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Pattern
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.bind.annotation.RestControllerAdvice
import java.security.MessageDigest
import java.sql.Timestamp
import java.time.Clock
import java.time.Instant
import java.util.Locale
import java.util.UUID

data class WebActionRequest(
    val idempotencyKey: UUID,
    @field:NotBlank @field:Pattern(regexp = "de|en") val locale: String,
    @field:Valid val proposal: ActionProposal,
    val conversationId: UUID? = null,
)

data class WebActionIntentRequest(
    val idempotencyKey: UUID,
    @field:NotBlank @field:Size(max = 2_000) val message: String,
    @field:NotBlank @field:Pattern(regexp = "de|en") val locale: String,
    @field:Size(max = 6) val priorMessages: List<ActionPriorMessage> = emptyList(),
    val conversationId: UUID? = null,
)

data class WebActionAttempt(val kind: String, val code: String? = null, val renderedText: String? = null, val outcome: ActionOutcome? = null)

data class ActionExecutionRecord(
    val correlationId: UUID,
    val requestHash: String,
    val status: String,
    val outcomeJson: String?,
)

interface ActionExecutionRepository {
    fun claim(ownerId: UUID, idempotencyKey: UUID, correlationId: UUID, requestHash: String, now: Instant): Boolean
    fun find(ownerId: UUID, idempotencyKey: UUID): ActionExecutionRecord?
    fun complete(ownerId: UUID, idempotencyKey: UUID, outcomeJson: String, now: Instant): Boolean
}

@Repository
class JdbcActionExecutionRepository(private val jdbc: JdbcClient) : ActionExecutionRepository {
    override fun claim(ownerId: UUID, idempotencyKey: UUID, correlationId: UUID, requestHash: String, now: Instant) =
        jdbc.sql("""INSERT INTO action_execution(id,owner_id,idempotency_key,correlation_id,request_hash,status,created_at)
            VALUES (:id,:ownerId,:key,:correlationId,:requestHash,'pending',:now)
            ON CONFLICT (owner_id,idempotency_key) DO NOTHING""")
            .param("id", UUID.randomUUID()).param("ownerId", ownerId).param("key", idempotencyKey)
            .param("correlationId", correlationId).param("requestHash", requestHash)
            .param("now", Timestamp.from(now)).update() == 1

    override fun find(ownerId: UUID, idempotencyKey: UUID): ActionExecutionRecord? = jdbc.sql(
        "SELECT correlation_id,request_hash,status,outcome FROM action_execution WHERE owner_id=:ownerId AND idempotency_key=:key",
    ).param("ownerId", ownerId).param("key", idempotencyKey).query { rs, _ ->
        ActionExecutionRecord(
            rs.getObject("correlation_id", UUID::class.java), rs.getString("request_hash"),
            rs.getString("status"), rs.getString("outcome"),
        )
    }.optional().orElse(null)

    override fun complete(ownerId: UUID, idempotencyKey: UUID, outcomeJson: String, now: Instant) = jdbc.sql(
        """UPDATE action_execution SET status='completed',outcome=CAST(:outcome AS jsonb),completed_at=:now
           WHERE owner_id=:ownerId AND idempotency_key=:key AND status='pending'""",
    ).param("outcome", outcomeJson).param("now", Timestamp.from(now)).param("ownerId", ownerId)
        .param("key", idempotencyKey).update() == 1
}

@Service
class ActionExecutionService(
    private val executions: ActionExecutionRepository,
    private val orchestrator: ActionOrchestrator,
    private val clock: Clock = Clock.systemUTC(),
    private val mapper: ObjectMapper = jacksonObjectMapper(),
) {
    fun execute(context: ActionContext, proposal: ActionProposal): ActionOutcome {
        val requestHash = sha256(mapper.writeValueAsBytes(mapOf(
            "channel" to context.channel.value,
            "locale" to context.locale.language,
            "sessionId" to context.sessionId,
            "conversationId" to context.conversationId,
            "proposal" to proposal,
        )))
        if (!executions.claim(context.ownerId, context.idempotencyKey, context.correlationId, requestHash, clock.instant())) {
            val existing = executions.find(context.ownerId, context.idempotencyKey) ?: throw ActionExecutionConflictException()
            if (existing.requestHash != requestHash) throw ActionIdempotencyMismatchException()
            if (existing.status != "completed" || existing.outcomeJson == null) throw ActionExecutionPendingException()
            return mapper.readValue(existing.outcomeJson, ActionOutcome::class.java)
        }
        val outcome = orchestrator.execute(context, proposal)
        check(executions.complete(context.ownerId, context.idempotencyKey, mapper.writeValueAsString(outcome), clock.instant()))
        return outcome
    }

    private fun sha256(value: ByteArray) = MessageDigest.getInstance("SHA-256").digest(value).joinToString("") { "%02x".format(it) }

}

@Service
class WebActionService(private val executions: ActionExecutionService) {
    fun execute(ownerId: UUID, request: WebActionRequest): ActionOutcome = executions.execute(
        ActionContext(
            ownerId, ActivityActorType.USER, ownerId.toString(), InteractionChannel.WEB,
            Locale.forLanguageTag(request.locale), UUID.randomUUID(), request.idempotencyKey,
            conversationId = request.conversationId,
        ),
        request.proposal,
    )
}

@Service
class WebActionIntentService(
    private val proposals: DeviceProposalProvider,
    private val actions: WebActionService,
    private val renderer: ActionResultRenderer,
) {
    fun execute(ownerId: UUID, request: WebActionIntentRequest): WebActionAttempt = when (
        val result = proposals.propose(ownerId, request.message.trim(), request.locale, request.priorMessages)
    ) {
        is ProposalResult.Proposed -> actions.execute(ownerId, WebActionRequest(
                request.idempotencyKey, request.locale, result.proposal, request.conversationId,
            )).let { WebActionAttempt("action", it.code, renderer.render(it, result.proposal, request.locale), it) }
        ProposalResult.None -> WebActionAttempt("none")
        ProposalResult.Ambiguous -> WebActionAttempt("rejected", "target.ambiguous", renderer.rejection("target.ambiguous", request.locale))
        ProposalResult.Invalid -> WebActionAttempt("rejected", "proposal.invalid", renderer.rejection("proposal.invalid", request.locale))
        ProposalResult.Unavailable -> WebActionAttempt(
            "unavailable", "proposal.unavailable",
            if (request.locale == "de") "Ich konnte die Aktion gerade nicht sicher prüfen." else "I couldn't safely evaluate that action right now.",
        )
    }
}

@Service
class ActionResultRenderer {
    fun render(outcome: ActionOutcome, proposal: DeviceActionProposal, locale: String): String {
        val name = outcome.targets.singleOrNull()?.displayName
        if (outcome.status == ActionOutcomeStatus.SUCCEEDED) {
            if (name != null && proposal.capability == "power.set") {
                val state = if (proposal.arguments.on == true) if (locale == "de") "eingeschaltet" else "turned on"
                    else if (locale == "de") "ausgeschaltet" else "turned off"
                return if (locale == "de") "„$name“ ist jetzt $state." else "“$name” is now $state."
            }
            if (name != null && proposal.capability == "light.setBrightness") return if (locale == "de")
                "„$name“ ist jetzt auf ${proposal.arguments.brightness} % eingestellt."
            else "“$name” is now set to ${proposal.arguments.brightness}%."
            return if (locale == "de") "Erledigt." else "Done."
        }
        return rejection(outcome.code, locale)
    }

    fun rejection(code: String, locale: String) = when (code) {
        "target.ambiguous" -> if (locale == "de") "Das Ziel ist nicht eindeutig." else "That target is ambiguous."
        "target.not_found", "proposal.invalid" -> if (locale == "de") "Ich konnte das Ziel nicht finden." else "I couldn't find that target."
        "device.offline" -> if (locale == "de") "Das Gerät ist momentan nicht erreichbar." else "The device is currently unavailable."
        "action.denied" -> if (locale == "de") "Diese Aktion ist nicht erlaubt." else "That action isn't allowed."
        else -> if (locale == "de") "Das hat nicht funktioniert." else "That didn't work."
    }
}

@RestController
@RequestMapping("/v1/actions")
class ActionController(private val actions: WebActionService, private val intents: WebActionIntentService) {
    @PostMapping
    fun execute(@Valid @RequestBody body: WebActionRequest, request: HttpServletRequest) =
        actions.execute(request.ownerId(), body)

    @PostMapping("/interpret")
    fun interpret(@Valid @RequestBody body: WebActionIntentRequest, request: HttpServletRequest) =
        intents.execute(request.ownerId(), body)

    private fun HttpServletRequest.ownerId() =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw ActionUnauthenticatedException()
}

class ActionExecutionPendingException : RuntimeException()
class ActionExecutionConflictException : RuntimeException()
class ActionIdempotencyMismatchException : RuntimeException()
class ActionUnauthenticatedException : RuntimeException()

@RestControllerAdvice
class ActionEndpointErrorHandler {
    @ExceptionHandler(ActionExecutionPendingException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun pending() = mapOf("code" to "ACTION_IN_PROGRESS")

    @ExceptionHandler(ActionExecutionConflictException::class, ActionIdempotencyMismatchException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun conflict() = mapOf("code" to "ACTION_IDEMPOTENCY_CONFLICT")

    @ExceptionHandler(ActionUnauthenticatedException::class)
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    fun unauthenticated() = mapOf("code" to "UNAUTHENTICATED")
}

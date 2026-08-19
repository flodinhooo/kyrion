package dev.kyrion.core.action

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Pattern
import org.springframework.http.HttpStatus
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
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
class WebActionService(
    private val executions: ActionExecutionRepository,
    private val orchestrator: ActionOrchestrator,
    private val clock: Clock = Clock.systemUTC(),
    private val mapper: ObjectMapper = jacksonObjectMapper(),
) {
    @Transactional
    fun execute(ownerId: UUID, request: WebActionRequest): ActionOutcome {
        val requestHash = sha256(mapper.writeValueAsBytes(request.copy(idempotencyKey = ZERO_UUID)))
        val correlationId = UUID.randomUUID()
        if (!executions.claim(ownerId, request.idempotencyKey, correlationId, requestHash, clock.instant())) {
            val existing = executions.find(ownerId, request.idempotencyKey) ?: throw ActionExecutionConflictException()
            if (existing.requestHash != requestHash) throw ActionIdempotencyMismatchException()
            if (existing.status != "completed" || existing.outcomeJson == null) throw ActionExecutionPendingException()
            return mapper.readValue(existing.outcomeJson, ActionOutcome::class.java)
        }
        val outcome = orchestrator.execute(
            ActionContext(
                ownerId, ActivityActorType.USER, ownerId.toString(), InteractionChannel.WEB,
                Locale.forLanguageTag(request.locale), correlationId, request.idempotencyKey,
                conversationId = request.conversationId,
            ),
            request.proposal,
        )
        check(executions.complete(ownerId, request.idempotencyKey, mapper.writeValueAsString(outcome), clock.instant()))
        return outcome
    }

    private fun sha256(value: ByteArray) = MessageDigest.getInstance("SHA-256").digest(value).joinToString("") { "%02x".format(it) }

    companion object { private val ZERO_UUID = UUID(0, 0) }
}

@RestController
@RequestMapping("/v1/actions")
class ActionController(private val actions: WebActionService) {
    @PostMapping
    fun execute(@Valid @RequestBody body: WebActionRequest, request: HttpServletRequest) =
        actions.execute(request.ownerId(), body)

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

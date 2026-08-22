package dev.kyrion.core.retention

import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import dev.kyrion.core.security.UnauthenticatedException
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.Pattern
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController
import java.sql.Timestamp
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID
import org.springframework.http.HttpStatus
import org.springframework.transaction.support.TransactionTemplate
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.ResponseStatus

data class RetentionPolicy(
    val conversations: String,
    val activity: String,
    val personalMemory: String,
    val updatedAt: Instant?,
    val enforcementActive: Boolean = false,
    val manualCleanupAvailable: Boolean = true,
)

data class RetentionPolicyRequest(
    @field:Pattern(regexp = POLICY_PATTERN) val conversations: String,
    @field:Pattern(regexp = POLICY_PATTERN) val activity: String,
    @field:Pattern(regexp = POLICY_PATTERN) val personalMemory: String,
)

data class RetentionDomainPreview(val policy: String, val cutoff: Instant?, val records: Int)
data class RetentionCleanupPreview(
    val generatedAt: Instant,
    val conversations: RetentionDomainPreview,
    val activity: RetentionDomainPreview,
    val personalMemory: RetentionDomainPreview,
)
data class RetentionCleanupRequest(val confirmation: String)
data class RetentionCleanupResult(
    val completedAt: Instant,
    val conversationsDeleted: Int,
    val activityDeleted: Int,
    val personalMemoriesDeleted: Int,
)

private const val POLICY_PATTERN = "keep_forever|30_days|90_days|365_days|3_years"

@RestController
@RequestMapping("/v1/retention")
class RetentionPolicyController(
    private val jdbc: JdbcClient,
    private val activityService: ActivityService,
    private val transactions: TransactionTemplate,
    private val clock: Clock = Clock.systemUTC(),
) {
    @GetMapping
    fun get(request: HttpServletRequest): RetentionPolicy = load(request.ownerId())

    @PutMapping
    fun update(@Valid @RequestBody body: RetentionPolicyRequest, request: HttpServletRequest): RetentionPolicy {
        val ownerId = request.ownerId()
        val now = clock.instant()
        jdbc.sql(
            """INSERT INTO owner_retention_policy
               (owner_id, conversation_policy, activity_policy, personal_memory_policy, updated_at)
               VALUES (:ownerId, :conversations, :activity, :memory, :updatedAt)
               ON CONFLICT (owner_id) DO UPDATE SET conversation_policy = EXCLUDED.conversation_policy,
                 activity_policy = EXCLUDED.activity_policy, personal_memory_policy = EXCLUDED.personal_memory_policy,
                 updated_at = EXCLUDED.updated_at""",
        ).param("ownerId", ownerId).param("conversations", body.conversations).param("activity", body.activity)
            .param("memory", body.personalMemory).param("updatedAt", Timestamp.from(now)).update()
        activityService.record(
            ActivityCategory.SECURITY, "retention.policy.updated", ActivityStatus.SUCCEEDED,
            ActivityActorType.USER, "kyrion-core", "retention.policy.updated",
            actorId = ownerId.toString(), ownerId = ownerId,
        )
        return RetentionPolicy(body.conversations, body.activity, body.personalMemory, now)
    }

    @GetMapping("/preview")
    fun preview(request: HttpServletRequest): RetentionCleanupPreview {
        val ownerId = request.ownerId()
        return preview(ownerId, load(ownerId), clock.instant())
    }

    @PostMapping("/cleanup")
    fun cleanup(@RequestBody body: RetentionCleanupRequest, request: HttpServletRequest): RetentionCleanupResult {
        if (body.confirmation != "DELETE") throw RetentionCleanupConfirmationException()
        val ownerId = request.ownerId()
        val now = clock.instant()
        return transactions.execute {
            val current = preview(ownerId, load(ownerId), now)
            val memoriesDeleted = deleteBefore("personal_memory", "updated_at", ownerId, current.personalMemory.cutoff)
            val conversationsDeleted = deleteBefore("conversation", "updated_at", ownerId, current.conversations.cutoff)
            val activityDeleted = deleteBefore("activity_event", "occurred_at", ownerId, current.activity.cutoff)
            activityService.record(
                ActivityCategory.SECURITY, "retention.cleanup.executed", ActivityStatus.SUCCEEDED,
                ActivityActorType.USER, "kyrion-core", "retention.cleanup.executed",
                actorId = ownerId.toString(), ownerId = ownerId,
            )
            RetentionCleanupResult(now, conversationsDeleted, activityDeleted, memoriesDeleted)
        }
    }

    private fun preview(ownerId: UUID, policy: RetentionPolicy, now: Instant) = RetentionCleanupPreview(
        now,
        domainPreview("conversation", "updated_at", ownerId, policy.conversations, now),
        domainPreview("activity_event", "occurred_at", ownerId, policy.activity, now),
        domainPreview("personal_memory", "updated_at", ownerId, policy.personalMemory, now),
    )

    private fun domainPreview(table: String, timestampColumn: String, ownerId: UUID, policy: String, now: Instant): RetentionDomainPreview {
        val cutoff = cutoff(policy, now) ?: return RetentionDomainPreview(policy, null, 0)
        val records = jdbc.sql("SELECT COUNT(*) FROM $table WHERE owner_id=:ownerId AND $timestampColumn<:cutoff")
            .param("ownerId", ownerId).param("cutoff", Timestamp.from(cutoff)).query(Int::class.java).single()
        return RetentionDomainPreview(policy, cutoff, records)
    }

    private fun deleteBefore(table: String, timestampColumn: String, ownerId: UUID, cutoff: Instant?): Int {
        if (cutoff == null) return 0
        return jdbc.sql("DELETE FROM $table WHERE owner_id=:ownerId AND $timestampColumn<:cutoff")
            .param("ownerId", ownerId).param("cutoff", Timestamp.from(cutoff)).update()
    }

    private fun cutoff(policy: String, now: Instant): Instant? = when (policy) {
        "keep_forever" -> null
        "30_days" -> now.minusSeconds(30L * 24 * 60 * 60)
        "90_days" -> now.minusSeconds(90L * 24 * 60 * 60)
        "365_days" -> now.minusSeconds(365L * 24 * 60 * 60)
        "3_years" -> now.atZone(ZoneOffset.UTC).minusYears(3).toInstant()
        else -> error("Unsupported persisted retention policy: $policy")
    }

    private fun load(ownerId: UUID): RetentionPolicy = jdbc.sql(
        """SELECT conversation_policy, activity_policy, personal_memory_policy, updated_at
           FROM owner_retention_policy WHERE owner_id = :ownerId""",
    ).param("ownerId", ownerId).query { rs, _ ->
        RetentionPolicy(
            rs.getString("conversation_policy"), rs.getString("activity_policy"),
            rs.getString("personal_memory_policy"), rs.getTimestamp("updated_at").toInstant(),
        )
    }.optional().orElse(RetentionPolicy("keep_forever", "keep_forever", "keep_forever", null))

    private fun HttpServletRequest.ownerId() =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw UnauthenticatedException()
}

class RetentionCleanupConfirmationException : RuntimeException()

@org.springframework.web.bind.annotation.RestControllerAdvice
class RetentionCleanupErrorHandler {
    @ExceptionHandler(RetentionCleanupConfirmationException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun confirmation() = mapOf("code" to "RETENTION_CLEANUP_CONFIRMATION_REQUIRED")
}

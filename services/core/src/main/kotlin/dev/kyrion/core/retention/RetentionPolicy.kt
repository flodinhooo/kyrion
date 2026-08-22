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
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController
import java.sql.Timestamp
import java.time.Clock
import java.time.Instant
import java.util.UUID

data class RetentionPolicy(
    val conversations: String,
    val activity: String,
    val personalMemory: String,
    val updatedAt: Instant?,
    val enforcementActive: Boolean = false,
)

data class RetentionPolicyRequest(
    @field:Pattern(regexp = POLICY_PATTERN) val conversations: String,
    @field:Pattern(regexp = POLICY_PATTERN) val activity: String,
    @field:Pattern(regexp = POLICY_PATTERN) val personalMemory: String,
)

private const val POLICY_PATTERN = "keep_forever|30_days|90_days|365_days|3_years"

@RestController
@RequestMapping("/v1/retention")
class RetentionPolicyController(
    private val jdbc: JdbcClient,
    private val activityService: ActivityService,
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

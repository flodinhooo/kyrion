package dev.kyrion.core.security

import java.util.UUID
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Service

data class TenantActor(val userId: UUID, val spaceId: UUID)

/** Explicit context for HTTP, workers and asynchronous operations; no thread-local identity. */
@Service
class TenantBoundary(
    private val jdbc: JdbcClient,
    private val clock: java.time.Clock = java.time.Clock.systemUTC(),
) {
    fun actor(user: UUID): TenantActor =
        jdbc
            .sql(
                """SELECT u.space_id FROM user_account u JOIN kyrion_space s ON s.id=u.space_id
        LEFT JOIN business_identity_policy p ON p.space_id=s.id
        WHERE u.id=:user AND u.enabled AND s.status='ACTIVE' AND (COALESCE(p.mode,'OFF')='OFF' OR EXISTS
        (SELECT 1 FROM account_email_identity e JOIN business_domain d ON d.space_id=e.space_id
         AND d.domain=split_part(e.email,'@',2) AND d.allowed
         WHERE e.user_id=u.id AND e.space_id=u.space_id AND e.proof_method='SMTP'))"""
            )
            .param("user", user)
            .query(UUID::class.java)
            .optional()
            .orElse(null)
            ?.let { TenantActor(user, it) } ?: throw ForbiddenException()

    fun workspace(space: UUID) {
        if (
            !jdbc
                .sql(
                    "SELECT EXISTS(SELECT 1 FROM kyrion_space s JOIN user_account u ON u.id=s.id AND u.space_id=s.id WHERE s.id=:space AND s.status='ACTIVE' AND u.enabled)"
                )
                .param("space", space)
                .query(Boolean::class.java)
                .single()
        )
            throw ForbiddenException()
    }

    fun voice(space: UUID) {
        workspace(space)
        if (
            jdbc
                .sql("SELECT type FROM kyrion_space WHERE id=:space")
                .param("space", space)
                .query(String::class.java)
                .single() == "BUSINESS"
        )
            throw IdentityPolicyException("BUSINESS_VOICE_IDENTITY_REQUIRED")
    }

    fun allowsLegacyProposal(space: UUID): Boolean {
        workspace(space)
        return jdbc
            .sql(
                "SELECT type='HOME' AND NOT EXISTS(SELECT 1 FROM ai_workspace_policy WHERE owner_id=:space) FROM kyrion_space WHERE id=:space"
            )
            .param("space", space)
            .query(Boolean::class.java)
            .single()
    }

    fun reactivated(user: UUID) {
        val context = actor(user)
        val eligible =
            jdbc
                .sql(
                    """SELECT NOT EXISTS(SELECT 1 FROM business_identity_policy WHERE space_id=:space AND mode='STRICT')
            OR EXISTS(SELECT 1 FROM account_email_identity e JOIN business_domain d ON d.space_id=e.space_id
              AND d.domain=split_part(e.email,'@',2) WHERE e.user_id=:user AND e.space_id=:space
              AND e.proof_method='SMTP' AND d.allowed AND d.verified_until>:now)"""
                )
                .param("space", context.spaceId)
                .param("now", java.sql.Timestamp.from(clock.instant()))
                .param("user", user)
                .query(Boolean::class.java)
                .single()
        if (!eligible) throw ForbiddenException()
    }

    fun personal(user: UUID, owner: UUID): TenantActor =
        actor(user).also { if (user != owner) throw ForbiddenException() }

    fun shared(user: UUID, space: UUID): TenantActor =
        actor(user).also { if (it.spaceId != space) throw ForbiddenException() }
}

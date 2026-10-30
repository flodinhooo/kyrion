package dev.kyrion.core.security

import dev.kyrion.core.activity.*
import java.security.MessageDigest
import java.sql.Timestamp
import java.time.Clock
import java.time.Instant
import java.util.UUID
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional

data class EmailIdentityView(
    val email: String?,
    val pendingEmail: String?,
    val status: String,
    val smtpAvailable: Boolean,
)

data class BusinessDomainView(
    val domain: String,
    val allowed: Boolean,
    val status: String,
    val verifiedUntil: Instant?,
)

data class BusinessPolicyView(
    val mode: String,
    val domains: List<BusinessDomainView>,
    val recoveryConfigured: Boolean,
)

data class DomainChallengeView(val name: String, val value: String, val expiresAt: Instant)

data class BusinessPolicyRequest(
    val mode: String,
    val domains: Set<String>,
    val confirmRevokeInvitations: Boolean = false,
)

@Service
class BusinessIdentityService(
    private val jdbc: JdbcClient,
    private val rbac: RbacService,
    private val activity: ActivityService,
    private val delivery: VerificationDelivery,
    private val dns: DomainTxtLookup,
    private val clock: Clock = Clock.systemUTC(),
) {
    private val verificationAttempts = LoginAttemptLimiter(clock)
    private val domainAttempts = InvitationCreationLimiter(clock)
    private val tokens = SessionTokenService()

    fun email(actor: UUID): EmailIdentityView {
        rbac.lockIdentity(actor)
        return jdbc
            .sql(
                "SELECT email,pending_email,proof_method FROM account_email_identity WHERE user_id=:actor AND space_id=:space"
            )
            .param("actor", actor)
            .param("space", rbac.workspace(actor))
            .query { rs, _ ->
                EmailIdentityView(
                    rs.getString(1),
                    rs.getString(2),
                    when {
                        rs.getString(3) == "SMTP" -> "VERIFIED"
                        rs.getString(3) == "LOCAL_ATTESTATION" -> "LOCALLY_ATTESTED"
                        else -> "PENDING"
                    },
                    delivery.available(),
                )
            }
            .optional()
            .orElse(EmailIdentityView(null, null, "MISSING", delivery.available()))
    }

    @Transactional
    fun requestEmail(actor: UUID, address: String) {
        val space = rbac.lockIdentity(actor)
        val email = BusinessAddress.email(address)
        requireAllowed(space, email)
        rateLimit(actor, null)
        if (!delivery.available()) throw IdentityPolicyException("SMTP_UNAVAILABLE")
        jdbc
            .sql(
                """INSERT INTO account_email_identity(user_id,space_id,pending_email) VALUES(:actor,:space,:email)
            ON CONFLICT(user_id) DO UPDATE SET pending_email=:email,updated_at=CURRENT_TIMESTAMP"""
            )
            .param("actor", actor)
            .param("space", space)
            .param("email", email)
            .update()
        issue(space, actor, null, email)
        audit("identity.email.challenge.created", actor, space)
    }

    @Transactional
    fun verifyEmail(actor: UUID, code: String) {
        val space = rbac.lockIdentity(actor)
        verificationAttempts.backoffFor(actor.toString())?.let {
            throw LoginRateLimitedException(it.retryAfter(clock.instant()))
        }
        val verified = proof(space, actor, null, null, code)
        if (verified == null) {
            verificationAttempts.recordFailure(actor.toString())
            throw IdentityPolicyException("EMAIL_PROOF_INVALID")
        }
        requireAllowed(space, verified)
        val updated =
            jdbc
                .sql(
                    """UPDATE account_email_identity SET email=:email,proof_method='SMTP',verified_at=:now,
            pending_email=NULL,updated_at=:now WHERE user_id=:actor AND space_id=:space AND pending_email=:email"""
                )
                .param("email", verified)
                .param("now", Timestamp.from(clock.instant()))
                .param("actor", actor)
                .param("space", space)
                .update()
        if (updated != 1) throw IdentityPolicyException("EMAIL_PROOF_INVALID")
        verificationAttempts.recordSuccess(actor.toString())
        audit("identity.email.verified", actor, space)
    }

    /** Public callers always receive the same accepted response, including unavailable SMTP. */
    @Transactional
    fun requestRegistrationEmail(invitation: String, address: String) {
        if (!invitation.matches(Regex("[A-Za-z0-9_-]{43}"))) return
        val email = runCatching { BusinessAddress.email(address) }.getOrNull() ?: return
        val hash = tokens.hash(invitation)
        val space =
            jdbc
                .sql(
                    """SELECT workspace_owner_id FROM registration_invitation WHERE token_hash=:hash
            AND revoked_at IS NULL AND redeemed_at IS NULL AND expires_at>:now AND use_count<max_uses
            AND (email_constraint IS NULL OR email_constraint=:email)"""
                )
                .param("hash", hash)
                .param("now", Timestamp.from(clock.instant()))
                .param("email", email)
                .query(UUID::class.java)
                .optional()
                .orElse(null) ?: return
        lock(space)
        if (!delivery.available()) return
        try {
            requireAllowed(space, email)
            rateLimit(null, hash)
        } catch (_: IdentityPolicyException) {
            return
        }
        issue(space, null, hash, email)
        audit("identity.registration.challenge.created", null, space)
    }

    /** Called inside the account-creation transaction, after the workspace lock. */
    fun enrollment(space: UUID, invitationHash: String, email: String?, code: String?): String? {
        val constraint =
            jdbc
                .sql(
                    "SELECT email_constraint FROM registration_invitation WHERE token_hash=:hash AND workspace_owner_id=:space"
                )
                .param("hash", invitationHash)
                .param("space", space)
                .query { rs, _ -> rs.getString(1) }
                .optional()
                .orElse(null)
        if (email == null && code == null && mode(space) == "OFF" && constraint == null) return null
        val normalized =
            runCatching { BusinessAddress.email(email ?: "") }
                .getOrElse { throw InvalidInvitationException() }
        if (constraint != null && constraint != normalized) throw InvalidInvitationException()
        val verified =
            proof(space, null, invitationHash, normalized, code ?: "")
                ?: throw InvalidInvitationException()
        try {
            requireAllowed(space, verified)
        } catch (_: IdentityPolicyException) {
            throw InvalidInvitationException()
        }
        return verified
    }

    fun attachVerified(account: UserAccount, email: String) {
        jdbc
            .sql(
                """INSERT INTO account_email_identity(user_id,space_id,email,proof_method,verified_at)
            VALUES(:user,:space,:email,'SMTP',:now)"""
            )
            .param("user", account.id)
            .param("space", account.resourceOwnerId)
            .param("email", email)
            .param("now", Timestamp.from(clock.instant()))
            .update()
        audit("identity.email.verified", account.id, account.resourceOwnerId)
    }

    fun invitationEmail(actor: UUID, address: String?): String? {
        val space = rbac.workspace(actor)
        val normalized = address?.let(BusinessAddress::email)
        if (mode(space) == "STRICT" && normalized == null)
            throw IdentityPolicyException("INVITATION_EMAIL_REQUIRED")
        if (normalized != null) requireAllowed(space, normalized)
        return normalized
    }

    fun policy(actor: UUID): BusinessPolicyView {
        val space = owner(actor)
        val domains =
            jdbc
                .sql(
                    "SELECT domain,allowed,verified_until FROM business_domain WHERE space_id=:space ORDER BY domain"
                )
                .param("space", space)
                .query { rs, _ ->
                    val until = rs.getTimestamp(3)?.toInstant()
                    BusinessDomainView(
                        rs.getString(1),
                        rs.getBoolean(2),
                        if (until?.isAfter(clock.instant()) == true) "VERIFIED" else "PENDING",
                        until,
                    )
                }
                .list()
        val recovery =
            jdbc
                .sql(
                    "SELECT EXISTS(SELECT 1 FROM space_recovery_material WHERE space_id=:space AND code_hash IS NOT NULL AND code_expires_at>:now)"
                )
                .param("space", space)
                .param("now", Timestamp.from(clock.instant()))
                .query(Boolean::class.java)
                .single()
        return BusinessPolicyView(mode(space), domains, recovery)
    }

    @Transactional
    fun challengeDomain(actor: UUID, value: String): DomainChallengeView {
        val space = owner(actor)
        domainAttempts.check(actor)
        val domain = BusinessAddress.domain(value)
        val token = tokens.create().rawToken
        val record = "kyrion-space=$space;token=$token"
        val expiry = clock.instant().plusSeconds(1800)
        // Rotating a challenge does not erase the last valid DNS proof.
        jdbc
            .sql(
                """INSERT INTO business_domain(space_id,domain,challenge_hash,challenge_expires_at) VALUES(:space,:domain,:hash,:expires)
            ON CONFLICT(space_id,domain) DO UPDATE SET challenge_hash=:hash,challenge_expires_at=:expires"""
            )
            .param("space", space)
            .param("domain", domain)
            .param("hash", tokens.hash(record))
            .param("expires", Timestamp.from(expiry))
            .update()
        audit("identity.domain.challenge.created", actor, space, tokens.hash(domain))
        return DomainChallengeView("_kyrion-verification.$domain", record, expiry)
    }

    @Transactional
    fun verifyDomain(actor: UUID, value: String): BusinessPolicyView {
        val space = owner(actor)
        domainAttempts.check(actor)
        val domain = BusinessAddress.domain(value)
        val expected =
            jdbc
                .sql(
                    "SELECT challenge_hash FROM business_domain WHERE space_id=:space AND domain=:domain AND challenge_expires_at>:now FOR UPDATE"
                )
                .param("space", space)
                .param("domain", domain)
                .param("now", Timestamp.from(clock.instant()))
                .query(String::class.java)
                .optional()
                .orElse(null) ?: throw IdentityPolicyException("DOMAIN_PROOF_INVALID")
        val records =
            runCatching { dns.records(domain) }
                .getOrElse { throw IdentityPolicyException("DNS_UNAVAILABLE") }
        if (
            records.none {
                MessageDigest.isEqual(tokens.hash(it).toByteArray(), expected.toByteArray())
            }
        )
            throw IdentityPolicyException("DOMAIN_PROOF_INVALID")
        jdbc
            .sql(
                "UPDATE business_domain SET verified_at=:now,verified_until=:until,challenge_expires_at=:now WHERE space_id=:space AND domain=:domain"
            )
            .param("now", Timestamp.from(clock.instant()))
            .param("until", Timestamp.from(clock.instant().plusSeconds(30 * 86400L)))
            .param("space", space)
            .param("domain", domain)
            .update()
        audit("identity.domain.verified", actor, space, tokens.hash(domain))
        return policy(actor)
    }

    @Transactional
    fun suspendDomain(actor: UUID, value: String): BusinessPolicyView {
        val space = owner(actor)
        val changed =
            jdbc
                .sql(
                    "UPDATE business_domain SET verified_until=:now,challenge_expires_at=:now WHERE space_id=:space AND domain=:domain"
                )
                .param("now", Timestamp.from(clock.instant()))
                .param("space", space)
                .param("domain", BusinessAddress.domain(value))
                .update()
        if (changed != 1) throw IdentityPolicyException("DOMAIN_PROOF_INVALID")
        audit("identity.domain.suspended", actor, space, tokens.hash(BusinessAddress.domain(value)))
        return policy(actor)
    }

    @Transactional
    fun updatePolicy(actor: UUID, request: BusinessPolicyRequest): BusinessPolicyView {
        val space = owner(actor)
        if (request.mode !in setOf("OFF", "STRICT") || request.domains.size > 20)
            throw IdentityPolicyException("POLICY_INVALID")
        val domains = request.domains.map(BusinessAddress::domain).toSet()
        jdbc
            .sql("UPDATE business_domain SET allowed=FALSE WHERE space_id=:space")
            .param("space", space)
            .update()
        domains.forEach { domain ->
            val updated =
                jdbc
                    .sql(
                        "UPDATE business_domain SET allowed=TRUE WHERE space_id=:space AND domain=:domain AND (:strict=FALSE OR verified_until>:now)"
                    )
                    .param("strict", request.mode == "STRICT")
                    .param("space", space)
                    .param("domain", domain)
                    .param("now", Timestamp.from(clock.instant()))
                    .update()
            if (updated != 1) throw IdentityPolicyException("DOMAIN_PROOF_REQUIRED")
        }
        if (request.mode == "STRICT") {
            if (!request.confirmRevokeInvitations || domains.isEmpty() || !delivery.available())
                throw IdentityPolicyException("POLICY_CONFIRMATION_REQUIRED")
            if (!policy(actor).recoveryConfigured)
                throw IdentityPolicyException("RECOVERY_REQUIRED")
            val excluded =
                jdbc
                    .sql(
                        """SELECT count(*) FROM user_account u LEFT JOIN account_email_identity e ON e.user_id=u.id AND e.space_id=u.space_id
                WHERE u.space_id=:space AND u.enabled AND (e.email IS NULL OR e.proof_method<>'SMTP' OR NOT EXISTS
                (SELECT 1 FROM business_domain d WHERE d.space_id=u.space_id AND d.allowed AND d.domain=split_part(e.email,'@',2)))"""
                    )
                    .param("space", space)
                    .query(Long::class.java)
                    .single()
            if (excluded > 0) throw IdentityPolicyException("POLICY_MEMBER_LOCKOUT")
            jdbc
                .sql(
                    "UPDATE registration_invitation SET revoked_at=:now WHERE workspace_owner_id=:space AND revoked_at IS NULL AND redeemed_at IS NULL"
                )
                .param("now", Timestamp.from(clock.instant()))
                .param("space", space)
                .update()
        }
        jdbc
            .sql(
                "INSERT INTO business_identity_policy(space_id,mode) VALUES(:space,:mode) ON CONFLICT(space_id) DO UPDATE SET mode=:mode,updated_at=CURRENT_TIMESTAMP"
            )
            .param("space", space)
            .param("mode", request.mode)
            .update()
        audit("identity.policy.updated", actor, space)
        return policy(actor)
    }

    private fun proof(
        space: UUID,
        actor: UUID?,
        invitation: String?,
        email: String?,
        code: String,
    ): String? {
        if (!code.matches(Regex("[A-Za-z0-9_-]{43}"))) return null
        val result =
            jdbc
                .sql(
                    """SELECT email FROM business_email_challenge WHERE token_hash=:hash AND space_id=:space
            AND ((CAST(:actor AS uuid) IS NOT NULL AND user_id=CAST(:actor AS uuid)) OR (CAST(:invitation AS varchar) IS NOT NULL AND invitation_hash=:invitation))
            AND consumed_at IS NULL AND expires_at>:now FOR UPDATE"""
                )
                .param("hash", tokens.hash(code))
                .param("space", space)
                .param("actor", actor, java.sql.Types.OTHER)
                .param("invitation", invitation, java.sql.Types.VARCHAR)
                .param("now", Timestamp.from(clock.instant()))
                .query(String::class.java)
                .optional()
                .orElse(null) ?: return null
        if (email != null && email != result) return null
        jdbc
            .sql("UPDATE business_email_challenge SET consumed_at=:now WHERE token_hash=:hash")
            .param("now", Timestamp.from(clock.instant()))
            .param("hash", tokens.hash(code))
            .update()
        return result
    }

    private fun issue(space: UUID, actor: UUID?, invitation: String?, email: String) {
        jdbc
            .sql(
                "UPDATE business_email_challenge SET consumed_at=:now WHERE (user_id=CAST(:actor AS uuid) OR invitation_hash=:invitation) AND consumed_at IS NULL"
            )
            .param("actor", actor, java.sql.Types.OTHER)
            .param("invitation", invitation, java.sql.Types.VARCHAR)
            .param("now", Timestamp.from(clock.instant()))
            .update()
        val token = tokens.create()
        jdbc
            .sql(
                "INSERT INTO business_email_challenge(token_hash,space_id,user_id,invitation_hash,email,created_at,expires_at) VALUES(:hash,:space,:actor,:invitation,:email,:now,:expires)"
            )
            .param("hash", token.tokenHash)
            .param("space", space)
            .param("actor", actor, java.sql.Types.OTHER)
            .param("invitation", invitation, java.sql.Types.VARCHAR)
            .param("email", email)
            .param("now", Timestamp.from(clock.instant()))
            .param("expires", Timestamp.from(clock.instant().plusSeconds(900)))
            .update()
        delivery.send(email, token.rawToken)
    }

    private fun rateLimit(actor: UUID?, invitation: String?) {
        val times =
            jdbc
                .sql(
                    "SELECT created_at FROM business_email_challenge WHERE (user_id=CAST(:actor AS uuid) OR invitation_hash=:invitation) AND created_at>:since ORDER BY created_at DESC"
                )
                .param("actor", actor, java.sql.Types.OTHER)
                .param("invitation", invitation, java.sql.Types.VARCHAR)
                .param("since", Timestamp.from(clock.instant().minusSeconds(3600)))
                .query { rs, _ -> rs.getTimestamp(1).toInstant() }
                .list()
        if (
            times.size >= 5 ||
                times.firstOrNull()?.isAfter(clock.instant().minusSeconds(60)) == true
        )
            throw IdentityPolicyException("VERIFICATION_RATE_LIMITED")
    }

    private fun owner(actor: UUID): UUID {
        val space = rbac.lockIdentity(actor)
        if (
            !rbac.isOwner(actor) ||
                jdbc
                    .sql("SELECT type FROM kyrion_space WHERE id=:space")
                    .param("space", space)
                    .query(String::class.java)
                    .single() != "BUSINESS"
        )
            throw ForbiddenException()
        return space
    }

    private fun mode(space: UUID) =
        jdbc
            .sql("SELECT mode FROM business_identity_policy WHERE space_id=:space")
            .param("space", space)
            .query(String::class.java)
            .optional()
            .orElse("OFF")

    private fun requireAllowed(space: UUID, email: String) {
        if (mode(space) == "OFF") return
        val allowed =
            jdbc
                .sql(
                    "SELECT EXISTS(SELECT 1 FROM business_domain WHERE space_id=:space AND domain=:domain AND allowed AND verified_until>:now)"
                )
                .param("space", space)
                .param("domain", email.substringAfter('@'))
                .param("now", Timestamp.from(clock.instant()))
                .query(Boolean::class.java)
                .single()
        if (!allowed) throw IdentityPolicyException("EMAIL_DOMAIN_NOT_ALLOWED")
    }

    private fun lock(space: UUID) {
        jdbc
            .sql("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:space AS text),23))")
            .param("space", space)
            .query { _, _ -> Unit }
            .single()
    }

    private fun audit(type: String, actor: UUID?, space: UUID, targetHash: String? = null) =
        activity.record(
            ActivityCategory.SECURITY,
            type,
            ActivityStatus.SUCCEEDED,
            if (actor == null) ActivityActorType.SYSTEM else ActivityActorType.USER,
            "kyrion-core",
            targetHash?.let { "domain:$it" } ?: type,
            actor?.toString(),
            ownerId = space,
        )
}

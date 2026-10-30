package dev.kyrion.core.security

import dev.kyrion.core.activity.*
import java.security.MessageDigest
import java.sql.Timestamp
import java.time.Clock
import java.util.UUID
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Service
import org.springframework.transaction.support.TransactionTemplate

class LocalRecoveryException : RuntimeException()

data class OpenedLocalRecovery(val session: String, val nextCode: String)

/** Deliberately has no HTTP controller. Only an interactive host CLI calls these operations. */
@Service
class LocalOwnerRecovery(
    private val jdbc: JdbcClient,
    private val transactions: TransactionTemplate,
    private val passwords: PasswordHashingService,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
    private val operator: String = "host-administrator",
) {
    private val tokens = SessionTokenService()

    fun provision(space: UUID, password: String, hostKey: String): String {
        val code = tokens.create().rawToken
        val authorized =
            transactions.execute {
                lock(space)
                val owner = root(space) ?: return@execute denied(space)
                if (!passwords.matches(password, owner.second) || !validToken(hostKey))
                    return@execute denied(space)
                if (
                    jdbc
                        .sql(
                            "SELECT EXISTS(SELECT 1 FROM space_recovery_material WHERE space_id=:space)"
                        )
                        .param("space", space)
                        .query(Boolean::class.java)
                        .single()
                )
                    return@execute denied(space)
                jdbc
                    .sql(
                        """INSERT INTO space_recovery_material(space_id,owner_id,host_key_hash,code_hash,code_expires_at)
                VALUES(:space,:owner,:host,:code,:expiry)"""
                    )
                    .param("space", space)
                    .param("owner", owner.first)
                    .param("host", hash("host", space, hostKey))
                    .param("code", hash("code", space, code))
                    .param("expiry", Timestamp.from(clock.instant().plusSeconds(365 * 86400L)))
                    .update()
                audit("identity.recovery.provisioned", space)
                true
            } == true
        if (!authorized) throw LocalRecoveryException()
        return code
    }

    fun open(space: UUID, hostKey: String, code: String): OpenedLocalRecovery {
        val nextCode = tokens.create().rawToken
        val session = tokens.create().rawToken
        val authorized =
            transactions.execute {
                lock(space)
                val row = material(space) ?: return@execute denied(space)
                if (
                    !matches(row.host, hash("host", space, hostKey)) ||
                        !matches(row.code, hash("code", space, code)) ||
                        !row.expires.isAfter(clock.instant()) ||
                        !validToken(hostKey) ||
                        !validToken(code) ||
                        root(space)?.first != row.owner
                )
                    return@execute denied(space)
                jdbc
                    .sql(
                        "UPDATE space_recovery_material SET code_hash=:code,generation=generation+1 WHERE space_id=:space"
                    )
                    .param("code", hash("code", space, nextCode))
                    .param("space", space)
                    .update()
                jdbc
                    .sql(
                        "INSERT INTO space_recovery_session(token_hash,space_id,generation,expires_at) VALUES(:hash,:space,:generation,:expiry)"
                    )
                    .param("hash", hash("session", space, session))
                    .param("space", space)
                    .param("generation", row.generation + 1)
                    .param("expiry", Timestamp.from(clock.instant().plusSeconds(300)))
                    .update()
                audit("identity.recovery.opened", space)
                true
            } == true
        if (!authorized) throw LocalRecoveryException()
        return OpenedLocalRecovery(session, nextCode)
    }

    fun rotate(space: UUID, hostKey: String, ownerPassword: String): String {
        val code = tokens.create().rawToken
        val authorized =
            transactions.execute {
                lock(space)
                val row = material(space) ?: return@execute denied(space)
                val owner = root(space) ?: return@execute denied(space)
                if (
                    !matches(row.host, hash("host", space, hostKey)) ||
                        !passwords.matches(ownerPassword, owner.second)
                )
                    return@execute denied(space)
                jdbc
                    .sql(
                        "UPDATE space_recovery_material SET code_hash=:code,code_expires_at=:expiry,generation=generation+1,updated_at=:now WHERE space_id=:space"
                    )
                    .param("code", hash("code", space, code))
                    .param("expiry", Timestamp.from(clock.instant().plusSeconds(365 * 86400L)))
                    .param("now", Timestamp.from(clock.instant()))
                    .param("space", space)
                    .update()
                audit("identity.recovery.rotated", space)
                true
            } == true
        if (!authorized) throw LocalRecoveryException()
        return code
    }

    fun complete(space: UUID, hostKey: String, session: String, password: String): String {
        if (password.length !in 12..200) throw LocalRecoveryException()
        val nextCode = tokens.create().rawToken
        val authorized =
            transactions.execute {
                lock(space)
                val row = material(space) ?: return@execute denied(space)
                val owner = root(space) ?: return@execute denied(space)
                val sessionHash = hash("session", space, session)
                val active =
                    jdbc
                        .sql(
                            "SELECT EXISTS(SELECT 1 FROM space_recovery_session WHERE token_hash=:hash AND space_id=:space AND generation=:generation AND consumed_at IS NULL AND expires_at>:now)"
                        )
                        .param("hash", sessionHash)
                        .param("space", space)
                        .param("generation", row.generation)
                        .param("now", Timestamp.from(clock.instant()))
                        .query(Boolean::class.java)
                        .single()
                if (
                    !active ||
                        !validToken(session) ||
                        !validToken(hostKey) ||
                        owner.first != row.owner ||
                        !matches(row.host, hash("host", space, hostKey)) ||
                        passwords.matches(password, owner.second)
                )
                    return@execute denied(space)
                val now = Timestamp.from(clock.instant())
                jdbc
                    .sql(
                        "UPDATE user_account SET password_hash=:hash,enabled=TRUE,updated_at=:now WHERE id=:owner AND space_id=:space"
                    )
                    .param("hash", passwords.hash(password))
                    .param("now", now)
                    .param("owner", row.owner)
                    .param("space", space)
                    .update()
                jdbc
                    .sql(
                        "UPDATE auth_session SET revoked_at=:now WHERE user_id=:owner AND revoked_at IS NULL"
                    )
                    .param("now", now)
                    .param("owner", row.owner)
                    .update()
                jdbc
                    .sql(
                        "UPDATE business_email_challenge SET consumed_at=:now WHERE user_id=:owner AND consumed_at IS NULL"
                    )
                    .param("now", now)
                    .param("owner", row.owner)
                    .update()
                jdbc
                    .sql(
                        "UPDATE registration_invitation SET revoked_at=:now WHERE created_by=:owner AND workspace_owner_id=:space AND revoked_at IS NULL AND redeemed_at IS NULL"
                    )
                    .param("now", now)
                    .param("owner", row.owner)
                    .param("space", space)
                    .update()
                jdbc
                    .sql(
                        "UPDATE space_recovery_session SET consumed_at=:now WHERE token_hash=:hash"
                    )
                    .param("now", now)
                    .param("hash", sessionHash)
                    .update()
                jdbc
                    .sql(
                        "UPDATE space_recovery_material SET code_hash=:hash,code_expires_at=:expiry,updated_at=:now WHERE space_id=:space"
                    )
                    .param("hash", hash("code", space, nextCode))
                    .param("expiry", Timestamp.from(clock.instant().plusSeconds(365 * 86400L)))
                    .param("now", now)
                    .param("space", space)
                    .update()
                audit("identity.recovery.completed", space)
                true
            } == true
        if (!authorized) throw LocalRecoveryException()
        return nextCode
    }

    fun attestEmail(
        space: UUID,
        hostKey: String,
        ownerPassword: String,
        user: UUID,
        address: String,
    ) {
        val email = BusinessAddress.email(address)
        val authorized =
            transactions.execute {
                lock(space)
                val row = material(space) ?: return@execute denied(space)
                val owner = root(space) ?: return@execute denied(space)
                val strict =
                    jdbc
                        .sql(
                            "SELECT EXISTS(SELECT 1 FROM business_identity_policy WHERE space_id=:space AND mode='STRICT')"
                        )
                        .param("space", space)
                        .query(Boolean::class.java)
                        .single()
                val member =
                    jdbc
                        .sql(
                            "SELECT EXISTS(SELECT 1 FROM user_account WHERE id=:user AND space_id=:space AND enabled)"
                        )
                        .param("user", user)
                        .param("space", space)
                        .query(Boolean::class.java)
                        .single()
                if (
                    strict ||
                        !member ||
                        !matches(row.host, hash("host", space, hostKey)) ||
                        !passwords.matches(ownerPassword, owner.second)
                )
                    return@execute denied(space)
                jdbc
                    .sql(
                        """INSERT INTO account_email_identity(user_id,space_id,email,proof_method,verified_at) VALUES(:user,:space,:email,'LOCAL_ATTESTATION',:now)
                ON CONFLICT(user_id) DO UPDATE SET email=:email,proof_method='LOCAL_ATTESTATION',verified_at=:now,pending_email=NULL,updated_at=:now"""
                    )
                    .param("user", user)
                    .param("space", space)
                    .param("email", email)
                    .param("now", Timestamp.from(clock.instant()))
                    .update()
                jdbc
                    .sql(
                        "UPDATE business_email_challenge SET consumed_at=:now WHERE user_id=:user AND consumed_at IS NULL"
                    )
                    .param("user", user)
                    .param("now", Timestamp.from(clock.instant()))
                    .update()
                audit("identity.email.locally_attested", space, target = user)
                true
            } == true
        if (!authorized) throw LocalRecoveryException()
    }

    private data class Material(
        val owner: UUID,
        val host: String,
        val code: String?,
        val expires: java.time.Instant,
        val generation: Long,
    )

    private fun material(space: UUID) =
        jdbc
            .sql("SELECT * FROM space_recovery_material WHERE space_id=:space FOR UPDATE")
            .param("space", space)
            .query { rs, _ ->
                Material(
                    rs.getObject("owner_id", UUID::class.java),
                    rs.getString("host_key_hash"),
                    rs.getString("code_hash"),
                    rs.getTimestamp("code_expires_at").toInstant(),
                    rs.getLong("generation"),
                )
            }
            .optional()
            .orElse(null)

    private fun root(space: UUID): Pair<UUID, String>? =
        jdbc
            .sql(
                "SELECT u.id,u.password_hash FROM user_account u JOIN kyrion_space s ON s.id=u.id WHERE s.id=:space AND s.status='ACTIVE' AND u.workspace_owner_id IS NULL"
            )
            .param("space", space)
            .query { rs, _ -> rs.getObject(1, UUID::class.java) to rs.getString(2) }
            .optional()
            .orElse(null)

    private fun hash(purpose: String, space: UUID, raw: String): String {
        val installation =
            jdbc
                .sql("SELECT id FROM installation_identity WHERE singleton")
                .query(UUID::class.java)
                .single()
        return tokens.hash("$purpose:$installation:$space:$raw")
    }

    private fun matches(expected: String?, actual: String) =
        expected != null && MessageDigest.isEqual(expected.toByteArray(), actual.toByteArray())

    private fun validToken(raw: String) = raw.matches(Regex("[A-Za-z0-9_-]{43}"))

    private fun lock(space: UUID) {
        jdbc
            .sql("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:space AS text),23))")
            .param("space", space)
            .query { _, _ -> Unit }
            .single()
    }

    private fun denied(space: UUID): Boolean {
        audit("identity.recovery.denied", space, ActivityStatus.DENIED)
        return false
    }

    private fun audit(
        type: String,
        space: UUID,
        status: ActivityStatus = ActivityStatus.SUCCEEDED,
        target: UUID? = null,
    ) =
        activity.record(
            ActivityCategory.SECURITY,
            type,
            status,
            ActivityActorType.SYSTEM,
            "local-security-admin",
            target?.toString() ?: type,
            actorId = "local:$operator".take(120),
            ownerId = space,
        )
}

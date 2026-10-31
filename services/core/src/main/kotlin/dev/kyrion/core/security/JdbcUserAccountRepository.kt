package dev.kyrion.core.security

import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.transaction.support.TransactionTemplate
import java.sql.ResultSet
import java.sql.Timestamp
import java.util.UUID

@Repository
class JdbcUserAccountRepository(
    private val jdbcClient: JdbcClient,
    private val transactions: TransactionTemplate,
    private val identities: BusinessIdentityService? = null,
) : UserAccountRepository {
    override fun exists(): Boolean = jdbcClient.sql("SELECT EXISTS (SELECT 1 FROM user_account)")
        .query(Boolean::class.java).single()

    override fun setupCompleted(): Boolean = jdbcClient.sql(
        "SELECT initialized OR EXISTS(SELECT 1 FROM user_account) FROM installation_bootstrap_state WHERE singleton",
    ).query(Boolean::class.java).single()

    override fun createOwner(account: UserAccount): UserAccount? = transactions.execute {
        jdbcClient.sql("SELECT pg_advisory_xact_lock(1264939342)")
            .query { _, _ -> Unit }
            .single()
        if (setupCompleted()) return@execute null
        jdbcClient.sql(
            """
            INSERT INTO user_account (id, username, password_hash, enabled, created_at, updated_at)
            VALUES (:id, :username, :passwordHash, :enabled, :createdAt, :updatedAt)
            """.trimIndent(),
        )
            .param("id", account.id)
            .param("username", account.username)
            .param("passwordHash", account.passwordHash)
            .param("enabled", account.enabled)
            .param("createdAt", Timestamp.from(account.createdAt))
            .param("updatedAt", Timestamp.from(account.updatedAt))
            .update()
        jdbcClient.sql("UPDATE installation_bootstrap_state SET initialized=TRUE WHERE singleton").update()
        account
    }

    override fun findByUsername(username: String): UserAccount? = jdbcClient.sql(
        "SELECT id, username, password_hash, enabled, created_at, updated_at, workspace_owner_id FROM user_account WHERE username = :username AND EXISTS (SELECT 1 FROM kyrion_space s WHERE s.id=user_account.space_id AND s.status='ACTIVE')",
    ).param("username", username).query(::map).optional().orElse(null)

    override fun findById(id: UUID): UserAccount? = jdbcClient.sql(
        "SELECT id, username, password_hash, enabled, created_at, updated_at, workspace_owner_id FROM user_account WHERE id = :id AND EXISTS (SELECT 1 FROM kyrion_space s WHERE s.id=user_account.space_id AND s.status='ACTIVE')",
    ).param("id", id).query(::map).optional().orElse(null)

    override fun createInvitation(invitation: RegistrationInvitation) {
        jdbcClient.sql(
            """INSERT INTO registration_invitation(token_hash, created_by, workspace_owner_id, expires_at)
               VALUES (:hash, :actor, :owner, :expires)""",
        ).param("hash", invitation.tokenHash).param("actor", invitation.createdBy)
            .param("owner", invitation.workspaceOwnerId).param("expires", Timestamp.from(invitation.expiresAt)).update()
    }

    override fun register(account: UserAccount, invitationHash: String, now: java.time.Instant): UserAccount? =
        registerVerified(account, invitationHash, now, null, null)

    override fun registerVerified(account: UserAccount, invitationHash: String, now: java.time.Instant, email: String?, proof: String?): UserAccount? = transactions.execute {
        val ownerId = jdbcClient.sql("SELECT workspace_owner_id FROM registration_invitation WHERE token_hash=:hash")
            .param("hash", invitationHash).query(UUID::class.java).optional().orElse(null) ?: return@execute null
        jdbcClient.sql("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:owner AS text),23))")
            .param("owner", ownerId).query { _, _ -> Unit }.single()
        val roleId = jdbcClient.sql(
            """SELECT r.id FROM registration_invitation i
               JOIN kyrion_space s ON s.id=i.workspace_owner_id AND s.status='ACTIVE'
               JOIN rbac_role r ON r.installation_owner_id=s.id
                 AND ((i.role_id IS NOT NULL AND r.id=i.role_id) OR (i.role_id IS NULL AND r.role_key=s.default_role_key))
               JOIN user_account inviter ON inviter.id=i.created_by AND inviter.space_id=s.id AND inviter.enabled
               WHERE i.token_hash=:hash AND i.revoked_at IS NULL AND i.redeemed_at IS NULL
                 AND i.expires_at>:now AND i.use_count<i.max_uses AND r.role_key<>'OWNER'
                 AND (inviter.id=s.id OR EXISTS (
                     SELECT 1 FROM rbac_user_role ur JOIN rbac_role ir ON ir.id=ur.role_id
                     WHERE ur.user_id=inviter.id AND ir.installation_owner_id=s.id AND ir.role_key='OWNER'
                 ) OR (
                     EXISTS (SELECT 1 FROM rbac_user_role ur JOIN rbac_role_permission rp ON rp.role_id=ur.role_id
                             WHERE ur.user_id=inviter.id AND rp.permission_key='invitations:create')
                     AND NOT EXISTS (SELECT 1 FROM rbac_role_permission grantp WHERE grantp.role_id=r.id
                         AND NOT EXISTS (SELECT 1 FROM rbac_user_role ur JOIN rbac_role_permission ownp ON ownp.role_id=ur.role_id
                                         WHERE ur.user_id=inviter.id AND ownp.permission_key=grantp.permission_key))
                 )) FOR UPDATE OF i""",
        ).param("hash", invitationHash).param("now", Timestamp.from(now))
            .query(UUID::class.java).optional().orElse(null) ?: return@execute null
        val verifiedEmail = identities?.enrollment(ownerId, invitationHash, email, proof)
        val created = account.copy(workspaceOwnerId = ownerId)
        val inserted = jdbcClient.sql(
            """INSERT INTO user_account (id, username, password_hash, enabled, created_at, updated_at, workspace_owner_id)
               VALUES (:id, :username, :passwordHash, :enabled, :createdAt, :updatedAt, :ownerId)
               ON CONFLICT (username) DO NOTHING""",
        ).param("id", created.id).param("username", created.username).param("passwordHash", created.passwordHash)
            .param("enabled", created.enabled).param("createdAt", Timestamp.from(created.createdAt))
            .param("updatedAt", Timestamp.from(created.updatedAt)).param("ownerId", ownerId).update()
        if (inserted != 1) {
            val sameSpace = jdbcClient.sql("SELECT EXISTS(SELECT 1 FROM user_account WHERE username=:name AND space_id=:owner)")
                .param("name", created.username).param("owner", ownerId).query(Boolean::class.java).single()
            if (sameSpace) throw UsernameTakenException()
            return@execute null
        }
        jdbcClient.sql("INSERT INTO rbac_user_role(user_id,role_id) VALUES(:user,:role)")
            .param("user", created.id).param("role", roleId).update()
        jdbcClient.sql("UPDATE registration_invitation SET use_count=use_count+1, redeemed_at=CASE WHEN use_count+1>=max_uses THEN CAST(:now AS timestamptz) ELSE NULL END WHERE token_hash=:hash")
            .param("now", Timestamp.from(now)).param("hash", invitationHash).update()
        if (verifiedEmail != null) identities?.attachVerified(created, verifiedEmail)
        created
    }

    override fun updatePassword(id: UUID, passwordHash: String, updatedAt: java.time.Instant): Boolean = jdbcClient.sql(
        "UPDATE user_account SET password_hash = :passwordHash, updated_at = :updatedAt WHERE id = :id AND enabled = TRUE",
    ).param("passwordHash", passwordHash).param("updatedAt", Timestamp.from(updatedAt)).param("id", id).update() == 1

    @Suppress("UNUSED_PARAMETER")
    private fun map(rs: ResultSet, row: Int) = UserAccount(
        id = rs.getObject("id", UUID::class.java),
        username = rs.getString("username"),
        passwordHash = rs.getString("password_hash"),
        enabled = rs.getBoolean("enabled"),
        createdAt = rs.getTimestamp("created_at").toInstant(),
        updatedAt = rs.getTimestamp("updated_at").toInstant(),
        workspaceOwnerId = rs.getObject("workspace_owner_id", UUID::class.java),
    )
}

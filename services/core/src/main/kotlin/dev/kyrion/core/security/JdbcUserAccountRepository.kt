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
) : UserAccountRepository {
    override fun exists(): Boolean = jdbcClient.sql("SELECT EXISTS (SELECT 1 FROM user_account)")
        .query(Boolean::class.java).single()

    override fun createOwner(account: UserAccount): UserAccount? = transactions.execute {
        jdbcClient.sql("SELECT pg_advisory_xact_lock(1264939342)")
            .query { _, _ -> Unit }
            .single()
        if (exists()) return@execute null
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
        account
    }

    override fun findByUsername(username: String): UserAccount? = jdbcClient.sql(
        "SELECT id, username, password_hash, enabled, created_at, updated_at, workspace_owner_id FROM user_account WHERE username = :username",
    ).param("username", username).query(::map).optional().orElse(null)

    override fun findById(id: UUID): UserAccount? = jdbcClient.sql(
        "SELECT id, username, password_hash, enabled, created_at, updated_at, workspace_owner_id FROM user_account WHERE id = :id",
    ).param("id", id).query(::map).optional().orElse(null)

    override fun createInvitation(invitation: RegistrationInvitation) {
        jdbcClient.sql(
            """INSERT INTO registration_invitation(token_hash, created_by, workspace_owner_id, expires_at)
               VALUES (:hash, :actor, :owner, :expires)""",
        ).param("hash", invitation.tokenHash).param("actor", invitation.createdBy)
            .param("owner", invitation.workspaceOwnerId).param("expires", Timestamp.from(invitation.expiresAt)).update()
    }

    override fun register(account: UserAccount, invitationHash: String, now: java.time.Instant): UserAccount? = transactions.execute {
        val ownerId = jdbcClient.sql(
            """SELECT workspace_owner_id FROM registration_invitation
               WHERE token_hash=:hash AND redeemed_at IS NULL AND expires_at > :now FOR UPDATE""",
        ).param("hash", invitationHash).param("now", Timestamp.from(now))
            .query(UUID::class.java).optional().orElse(null) ?: return@execute null
        val created = account.copy(workspaceOwnerId = ownerId)
        val inserted = jdbcClient.sql(
            """INSERT INTO user_account (id, username, password_hash, enabled, created_at, updated_at, workspace_owner_id)
               VALUES (:id, :username, :passwordHash, :enabled, :createdAt, :updatedAt, :ownerId)
               ON CONFLICT (username) DO NOTHING""",
        ).param("id", created.id).param("username", created.username).param("passwordHash", created.passwordHash)
            .param("enabled", created.enabled).param("createdAt", Timestamp.from(created.createdAt))
            .param("updatedAt", Timestamp.from(created.updatedAt)).param("ownerId", ownerId).update()
        if (inserted != 1) throw UsernameTakenException()
        jdbcClient.sql("UPDATE registration_invitation SET redeemed_at=:now WHERE token_hash=:hash")
            .param("now", Timestamp.from(now)).param("hash", invitationHash).update()
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

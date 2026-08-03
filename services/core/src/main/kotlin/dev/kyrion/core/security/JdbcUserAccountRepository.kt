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
        "SELECT id, username, password_hash, enabled, created_at, updated_at FROM user_account WHERE username = :username",
    ).param("username", username).query(::map).optional().orElse(null)

    override fun findById(id: UUID): UserAccount? = jdbcClient.sql(
        "SELECT id, username, password_hash, enabled, created_at, updated_at FROM user_account WHERE id = :id",
    ).param("id", id).query(::map).optional().orElse(null)

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
    )
}

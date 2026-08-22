package dev.kyrion.core.security

import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import java.sql.ResultSet
import java.sql.Timestamp
import java.time.Instant
import java.util.UUID

@Repository
class JdbcAuthSessionRepository(
    private val jdbcClient: JdbcClient,
) : AuthSessionRepository {
    override fun create(session: AuthSession): AuthSession {
        jdbcClient.sql(
            """
            INSERT INTO auth_session (
                id, user_id, token_hash, created_at, last_seen_at, expires_at, revoked_at
            ) VALUES (
                :id, :userId, :tokenHash, :createdAt, :lastSeenAt, :expiresAt, :revokedAt
            )
            """.trimIndent(),
        )
            .param("id", session.id)
            .param("userId", session.userId)
            .param("tokenHash", session.tokenHash)
            .param("createdAt", Timestamp.from(session.createdAt))
            .param("lastSeenAt", Timestamp.from(session.lastSeenAt))
            .param("expiresAt", Timestamp.from(session.expiresAt))
            .param("revokedAt", session.revokedAt?.let(Timestamp::from))
            .update()
        return session
    }

    override fun findByTokenHash(tokenHash: String): AuthSession? = jdbcClient.sql(
        """
        SELECT id, user_id, token_hash, created_at, last_seen_at, expires_at, revoked_at
        FROM auth_session
        WHERE token_hash = :tokenHash
        """.trimIndent(),
    )
        .param("tokenHash", tokenHash)
        .query(::mapSession)
        .optional()
        .orElse(null)

    override fun updateLastSeen(tokenHash: String, lastSeenAt: Instant) {
        jdbcClient.sql(
            """
            UPDATE auth_session
            SET last_seen_at = :lastSeenAt
            WHERE token_hash = :tokenHash AND revoked_at IS NULL
            """.trimIndent(),
        )
            .param("lastSeenAt", Timestamp.from(lastSeenAt))
            .param("tokenHash", tokenHash)
            .update()
    }

    override fun revoke(tokenHash: String, revokedAt: Instant): Boolean = jdbcClient.sql(
        """
        UPDATE auth_session
        SET revoked_at = :revokedAt
        WHERE token_hash = :tokenHash AND revoked_at IS NULL
        """.trimIndent(),
    )
        .param("revokedAt", Timestamp.from(revokedAt))
        .param("tokenHash", tokenHash)
        .update() == 1

    override fun findActiveForUser(userId: UUID, at: Instant): List<AuthSession> = jdbcClient.sql(
        """
        SELECT id, user_id, token_hash, created_at, last_seen_at, expires_at, revoked_at
        FROM auth_session
        WHERE user_id = :userId AND revoked_at IS NULL AND expires_at > :at
        ORDER BY last_seen_at DESC, created_at DESC
        """.trimIndent(),
    )
        .param("userId", userId)
        .param("at", Timestamp.from(at))
        .query(::mapSession)
        .list()

    override fun revokeForUser(userId: UUID, sessionId: UUID, revokedAt: Instant): Boolean = jdbcClient.sql(
        """
        UPDATE auth_session
        SET revoked_at = :revokedAt
        WHERE id = :sessionId AND user_id = :userId AND revoked_at IS NULL AND expires_at > :revokedAt
        """.trimIndent(),
    )
        .param("revokedAt", Timestamp.from(revokedAt))
        .param("sessionId", sessionId)
        .param("userId", userId)
        .update() == 1

    override fun revokeAllForUser(userId: UUID, revokedAt: Instant): Int = jdbcClient.sql(
        "UPDATE auth_session SET revoked_at = :revokedAt WHERE user_id = :userId AND revoked_at IS NULL",
    ).param("revokedAt", Timestamp.from(revokedAt)).param("userId", userId).update()

    @Suppress("UNUSED_PARAMETER")
    private fun mapSession(resultSet: ResultSet, rowNumber: Int): AuthSession = AuthSession(
        id = resultSet.getObject("id", UUID::class.java),
        userId = resultSet.getObject("user_id", UUID::class.java),
        tokenHash = resultSet.getString("token_hash"),
        createdAt = resultSet.getTimestamp("created_at").toInstant(),
        lastSeenAt = resultSet.getTimestamp("last_seen_at").toInstant(),
        expiresAt = resultSet.getTimestamp("expires_at").toInstant(),
        revokedAt = resultSet.getTimestamp("revoked_at")?.toInstant(),
    )
}

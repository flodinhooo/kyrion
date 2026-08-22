package dev.kyrion.core.security

import java.time.Instant
import java.util.UUID

interface AuthSessionRepository {
    fun create(session: AuthSession): AuthSession

    fun findByTokenHash(tokenHash: String): AuthSession?

    fun updateLastSeen(tokenHash: String, lastSeenAt: Instant)

    fun revoke(tokenHash: String, revokedAt: Instant): Boolean
    fun findActiveForUser(userId: UUID, at: Instant): List<AuthSession>
    fun revokeForUser(userId: UUID, sessionId: UUID, revokedAt: Instant): Boolean
    fun revokeAllForUser(userId: UUID, revokedAt: Instant): Int
}

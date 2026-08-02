package dev.kyrion.core.security

import java.time.Instant

interface AuthSessionRepository {
    fun create(session: AuthSession): AuthSession

    fun findByTokenHash(tokenHash: String): AuthSession?

    fun updateLastSeen(tokenHash: String, lastSeenAt: Instant)

    fun revoke(tokenHash: String, revokedAt: Instant): Boolean
}

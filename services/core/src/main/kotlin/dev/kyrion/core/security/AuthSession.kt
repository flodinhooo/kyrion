package dev.kyrion.core.security

import java.time.Instant
import java.util.UUID

data class AuthSession(
    val id: UUID,
    val userId: UUID,
    val tokenHash: String,
    val createdAt: Instant,
    val lastSeenAt: Instant,
    val expiresAt: Instant,
    val revokedAt: Instant?,
) {
    fun isActive(at: Instant): Boolean = revokedAt == null && expiresAt.isAfter(at)
}

data class CreatedSession(
    val session: AuthSession,
    val rawToken: String,
)

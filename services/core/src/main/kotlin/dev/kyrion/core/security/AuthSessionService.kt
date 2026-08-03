package dev.kyrion.core.security

import org.springframework.stereotype.Service
import java.time.Clock
import java.time.Duration
import java.util.UUID

@Service
class AuthSessionService(
    private val repository: AuthSessionRepository,
    private val tokenService: SessionTokenService,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun create(userId: UUID, lifetime: Duration = DEFAULT_LIFETIME): CreatedSession {
        require(!lifetime.isNegative && !lifetime.isZero) {
            "Session lifetime must be positive"
        }
        val now = clock.instant()
        val token = tokenService.create()
        val session = repository.create(
            AuthSession(
                id = UUID.randomUUID(),
                userId = userId,
                tokenHash = token.tokenHash,
                createdAt = now,
                lastSeenAt = now,
                expiresAt = now.plus(lifetime),
                revokedAt = null,
            ),
        )
        return CreatedSession(session = session, rawToken = token.rawToken)
    }

    fun authenticate(rawToken: String): AuthSession? {
        val tokenHash = tokenService.hash(rawToken)
        val session = repository.findByTokenHash(tokenHash) ?: return null
        val now = clock.instant()
        if (!session.isActive(now)) return null
        repository.updateLastSeen(tokenHash, now)
        return session.copy(lastSeenAt = now)
    }

    fun revoke(rawToken: String): Boolean = repository.revoke(
        tokenHash = tokenService.hash(rawToken),
        revokedAt = clock.instant(),
    )

    fun revokeAllForUser(userId: UUID): Int = repository.revokeAllForUser(userId, clock.instant())

    private companion object {
        val DEFAULT_LIFETIME: Duration = Duration.ofDays(7)
    }
}

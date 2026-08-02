package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID

class AuthSessionServiceTest {
    private val now = Instant.parse("2026-08-02T18:45:00Z")
    private val repository = InMemoryAuthSessionRepository()
    private val tokenService = SessionTokenService()
    private val service = AuthSessionService(
        repository,
        tokenService,
        Clock.fixed(now, ZoneOffset.UTC),
    )

    @Test
    fun `creates a seven day session without persisting its raw token`() {
        val userId = UUID.randomUUID()

        val created = service.create(userId)

        assertThat(created.session.userId).isEqualTo(userId)
        assertThat(created.session.createdAt).isEqualTo(now)
        assertThat(created.session.expiresAt).isEqualTo(now.plus(Duration.ofDays(7)))
        assertThat(created.session.tokenHash).isEqualTo(tokenService.hash(created.rawToken))
        assertThat(repository.session?.tokenHash).doesNotContain(created.rawToken)
    }

    @Test
    fun `authenticates an active session and updates last seen`() {
        val created = service.create(UUID.randomUUID())

        val authenticated = service.authenticate(created.rawToken)

        assertThat(authenticated?.id).isEqualTo(created.session.id)
        assertThat(repository.lastSeenUpdate).isEqualTo(now)
    }

    @Test
    fun `rejects expired and revoked sessions`() {
        val expired = service.create(UUID.randomUUID(), Duration.ofSeconds(1))
        repository.session = expired.session.copy(expiresAt = now)
        assertThat(service.authenticate(expired.rawToken)).isNull()

        val active = service.create(UUID.randomUUID())
        assertThat(service.revoke(active.rawToken)).isTrue()
        assertThat(service.authenticate(active.rawToken)).isNull()
    }
}

private class InMemoryAuthSessionRepository : AuthSessionRepository {
    var session: AuthSession? = null
    var lastSeenUpdate: Instant? = null

    override fun create(session: AuthSession): AuthSession = session.also { this.session = it }

    override fun findByTokenHash(tokenHash: String): AuthSession? =
        session?.takeIf { it.tokenHash == tokenHash }

    override fun updateLastSeen(tokenHash: String, lastSeenAt: Instant) {
        if (session?.tokenHash == tokenHash) {
            lastSeenUpdate = lastSeenAt
            session = session?.copy(lastSeenAt = lastSeenAt)
        }
    }

    override fun revoke(tokenHash: String, revokedAt: Instant): Boolean {
        val current = session?.takeIf { it.tokenHash == tokenHash && it.revokedAt == null }
            ?: return false
        session = current.copy(revokedAt = revokedAt)
        return true
    }
}

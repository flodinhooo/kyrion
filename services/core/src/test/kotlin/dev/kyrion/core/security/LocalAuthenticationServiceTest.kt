package dev.kyrion.core.security

import dev.kyrion.core.activity.ActivityEvent
import dev.kyrion.core.activity.ActivityEventRepository
import dev.kyrion.core.activity.ActivityService
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.time.Duration
import java.util.UUID

class LocalAuthenticationServiceTest {
    private val now = Instant.parse("2026-08-03T20:00:00Z")
    private val clock = MutableClock(now)
    private val users = InMemoryUserAccountRepository()
    private val sessions = InMemoryAuthSessionRepositoryForAuthentication()
    private val service = LocalAuthenticationService(
        users,
        PasswordHashingService(),
        AuthSessionService(sessions, SessionTokenService(), clock),
        ActivityService(InMemorySecurityActivityRepository(), clock),
        clock,
    )

    @Test
    fun `creates exactly one owner and immediately authenticates it`() {
        val owner = service.setup(" Flo ", "a-secure-local-password")

        assertThat(owner.user.username).isEqualTo("flo")
        assertThat(service.setupRequired()).isFalse()
        assertThat(service.authenticate(owner.session.rawToken)?.id).isEqualTo(owner.user.id)
        assertThatThrownBy { service.setup("other", "another-secure-password") }
            .isInstanceOf(SetupAlreadyCompletedException::class.java)
    }

    @Test
    fun `rejects invalid credentials and revokes logout session`() {
        val owner = service.setup("flo", "a-secure-local-password")
        assertThatThrownBy { service.login("flo", "definitely-the-wrong-password") }
            .isInstanceOf(InvalidCredentialsException::class.java)

        val loggedIn = service.login("FLO", "a-secure-local-password")
        assertThat(service.logout(loggedIn.session.rawToken, owner.user.id)).isTrue()
        assertThat(service.authenticate(loggedIn.session.rawToken)).isNull()
    }

    @Test
    fun `changes password and rotates all sessions`() {
        val owner = service.setup("flo", "a-secure-local-password")
        val changed = service.changePassword(owner.session.rawToken, "a-secure-local-password", "a-brand-new-password")

        assertThat(service.authenticate(owner.session.rawToken)).isNull()
        assertThat(service.authenticate(changed.session.rawToken)?.id).isEqualTo(owner.user.id)
        assertThatThrownBy { service.login("flo", "a-secure-local-password") }.isInstanceOf(InvalidCredentialsException::class.java)
        assertThat(service.login("flo", "a-brand-new-password").user.id).isEqualTo(owner.user.id)
    }

    @Test
    fun `temporarily backs off repeated login failures and resets after success`() {
        service.setup("flo", "a-secure-local-password")

        repeat(5) {
            assertThatThrownBy { service.login("FLO", "definitely-the-wrong-password") }
                .isInstanceOf(InvalidCredentialsException::class.java)
        }
        assertThatThrownBy { service.login("flo", "a-secure-local-password") }
            .isInstanceOfSatisfying(LoginRateLimitedException::class.java) { exception ->
                assertThat(exception.retryAfter).isEqualTo(Duration.ofSeconds(30))
            }

        clock.advance(Duration.ofSeconds(30))
        assertThat(service.login("flo", "a-secure-local-password").user.username).isEqualTo("flo")

        assertThatThrownBy { service.login("flo", "wrong-password-again") }
            .isInstanceOf(InvalidCredentialsException::class.java)
        assertThat(service.login("flo", "a-secure-local-password").user.username).isEqualTo("flo")
    }

    @Test
    fun `lists only owner sessions and selectively revokes another session`() {
        val current = service.setup("flo", "a-secure-local-password")
        val other = service.login("flo", "a-secure-local-password")

        val active = service.activeSessions(current.session.rawToken)

        assertThat(active).hasSize(2)
        assertThat(active.single { it.current }.id).isEqualTo(current.session.session.id)
        assertThat(active).allMatch { it.id == current.session.session.id || it.id == other.session.session.id }

        service.revokeSession(current.session.rawToken, other.session.session.id)
        assertThat(service.authenticate(other.session.rawToken)).isNull()
        assertThat(service.authenticate(current.session.rawToken)?.id).isEqualTo(current.user.id)
        assertThatThrownBy { service.revokeSession(current.session.rawToken, current.session.session.id) }
            .isInstanceOf(CurrentSessionRevocationException::class.java)
        assertThatThrownBy { service.revokeSession(current.session.rawToken, UUID.randomUUID()) }
            .isInstanceOf(AuthSessionNotFoundException::class.java)
    }
}

private class MutableClock(private var current: Instant) : Clock() {
    override fun getZone() = ZoneOffset.UTC
    override fun withZone(zone: java.time.ZoneId): Clock = this
    override fun instant(): Instant = current
    fun advance(duration: Duration) { current = current.plus(duration) }
}

private class InMemoryUserAccountRepository : UserAccountRepository {
    private var account: UserAccount? = null
    override fun exists() = account != null
    override fun createOwner(account: UserAccount): UserAccount? = if (this.account == null) account.also { this.account = it } else null
    override fun findByUsername(username: String) = account?.takeIf { it.username == username }
    override fun findById(id: UUID) = account?.takeIf { it.id == id }
    override fun updatePassword(id: UUID, passwordHash: String, updatedAt: Instant): Boolean {
        val current = account?.takeIf { it.id == id } ?: return false
        account = current.copy(passwordHash = passwordHash, updatedAt = updatedAt)
        return true
    }
}

private class InMemoryAuthSessionRepositoryForAuthentication : AuthSessionRepository {
    private val values = mutableMapOf<String, AuthSession>()
    override fun create(session: AuthSession) = session.also { values[it.tokenHash] = it }
    override fun findByTokenHash(tokenHash: String) = values[tokenHash]
    override fun updateLastSeen(tokenHash: String, lastSeenAt: Instant) { values[tokenHash]?.let { values[tokenHash] = it.copy(lastSeenAt = lastSeenAt) } }
    override fun revoke(tokenHash: String, revokedAt: Instant): Boolean {
        val value = values[tokenHash]?.takeIf { it.revokedAt == null } ?: return false
        values[tokenHash] = value.copy(revokedAt = revokedAt)
        return true
    }
    override fun findActiveForUser(userId: UUID, at: Instant): List<AuthSession> =
        values.values.filter { it.userId == userId && it.isActive(at) }
            .sortedWith(compareByDescending<AuthSession> { it.lastSeenAt }.thenByDescending { it.createdAt })
    override fun revokeForUser(userId: UUID, sessionId: UUID, revokedAt: Instant): Boolean {
        val entry = values.entries.firstOrNull { (_, value) ->
            value.id == sessionId && value.userId == userId && value.isActive(revokedAt)
        } ?: return false
        values[entry.key] = entry.value.copy(revokedAt = revokedAt)
        return true
    }
    override fun revokeAllForUser(userId: UUID, revokedAt: Instant): Int {
        var count = 0
        values.replaceAll { _, value -> if (value.userId == userId && value.revokedAt == null) { count++; value.copy(revokedAt = revokedAt) } else value }
        return count
    }
}

private class InMemorySecurityActivityRepository : ActivityEventRepository {
    private val events = mutableListOf<ActivityEvent>()
    override fun append(event: ActivityEvent) = event.also(events::add)
    override fun findRecent(limit: Int) = events.take(limit)
}

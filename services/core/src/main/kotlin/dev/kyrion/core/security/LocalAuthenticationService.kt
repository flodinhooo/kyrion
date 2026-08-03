package dev.kyrion.core.security

import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.time.Clock
import java.util.UUID

data class AuthenticatedOwner(val user: UserAccount, val session: CreatedSession)

@Service
class LocalAuthenticationService(
    private val users: UserAccountRepository,
    private val passwords: PasswordHashingService,
    private val sessions: AuthSessionService,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun setupRequired() = !users.exists()

    fun setup(username: String, password: String): AuthenticatedOwner {
        val normalized = normalizeUsername(username)
        val now = clock.instant()
        val account = UserAccount(UUID.randomUUID(), normalized, passwords.hash(password), true, now, now)
        val created = users.createOwner(account) ?: throw SetupAlreadyCompletedException()
        record("auth.owner.setup", ActivityStatus.SUCCEEDED, "activity.auth.ownerSetup", created.id)
        return AuthenticatedOwner(created, sessions.create(created.id))
    }

    fun login(username: String, password: String): AuthenticatedOwner {
        val account = users.findByUsername(normalizeUsername(username))
        if (account == null || !account.enabled || !passwords.matches(password, account.passwordHash)) {
            record("auth.login", ActivityStatus.DENIED, "activity.auth.loginFailed")
            throw InvalidCredentialsException()
        }
        record("auth.login", ActivityStatus.SUCCEEDED, "activity.auth.loginSucceeded", account.id)
        return AuthenticatedOwner(account, sessions.create(account.id))
    }

    fun authenticate(rawToken: String): UserAccount? {
        val session = sessions.authenticate(rawToken) ?: return null
        return users.findById(session.userId)?.takeIf { it.enabled }
    }

    fun logout(rawToken: String, actorId: UUID?): Boolean = sessions.revoke(rawToken).also { revoked ->
        if (revoked) record("auth.logout", ActivityStatus.SUCCEEDED, "activity.auth.logout", actorId)
    }

    @Transactional
    fun changePassword(rawToken: String, currentPassword: String, newPassword: String): AuthenticatedOwner {
        val account = authenticate(rawToken) ?: throw UnauthenticatedException()
        if (!passwords.matches(currentPassword, account.passwordHash)) {
            record("auth.password.change", ActivityStatus.DENIED, "activity.auth.passwordChangeFailed", account.id)
            throw InvalidCurrentPasswordException()
        }
        if (currentPassword == newPassword) throw PasswordUnchangedException()
        val now = clock.instant()
        val newHash = passwords.hash(newPassword)
        check(users.updatePassword(account.id, newHash, now))
        sessions.revokeAllForUser(account.id)
        val updated = account.copy(passwordHash = newHash, updatedAt = now)
        val created = sessions.create(account.id)
        record("auth.password.change", ActivityStatus.SUCCEEDED, "activity.auth.passwordChanged", account.id)
        return AuthenticatedOwner(updated, created)
    }

    private fun normalizeUsername(value: String) = value.trim().lowercase()

    private fun record(type: String, status: ActivityStatus, summary: String, actorId: UUID? = null) {
        activity.record(
            category = ActivityCategory.SECURITY,
            eventType = type,
            status = status,
            actorType = actorId?.let { ActivityActorType.USER } ?: ActivityActorType.SYSTEM,
            actorId = actorId?.toString(),
            source = "kyrion-core",
            summaryCode = summary,
        )
    }
}

class SetupAlreadyCompletedException : RuntimeException()
class InvalidCredentialsException : RuntimeException()
class InvalidCurrentPasswordException : RuntimeException()
class PasswordUnchangedException : RuntimeException()

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
data class ActiveSession(
    val id: UUID,
    val createdAt: java.time.Instant,
    val lastSeenAt: java.time.Instant,
    val expiresAt: java.time.Instant,
    val current: Boolean,
)

@Service
class LocalAuthenticationService(
    private val users: UserAccountRepository,
    private val passwords: PasswordHashingService,
    private val sessions: AuthSessionService,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
    private val loginAttempts: LoginAttemptLimiter = LoginAttemptLimiter(clock),
    private val invitationTokens: SessionTokenService = SessionTokenService(),
    private val rbac: RbacService? = null,
    private val bootstrap: FirstOwnerBootstrap? = null,
    private val spaces: SpaceService? = null,
    private val boundary: TenantBoundary? = null,
    private val registrationAttempts: LoginAttemptLimiter = LoginAttemptLimiter(clock),
) {
    fun setupRequired() = !users.setupCompleted()

    @Transactional
    fun createInvitation(rawToken: String): CreatedInvitation {
        val inviter = authenticatedSession(rawToken, touch = false)?.first ?: throw UnauthenticatedException()
        if (rbac != null) rbac.authorizeMutation(inviter.id, "invitations:create")
        else if (inviter.resourceOwnerId != inviter.id) throw InvitationForbiddenException()
        if (authenticatedSession(rawToken, touch = false) == null) throw UnauthenticatedException()
        spaces?.let {
            val issued = it.createInvitation(inviter.id, InvitationOptions())
            return CreatedInvitation(issued.code, issued.expiresAt)
        }
        val token = invitationTokens.create()
        val expiresAt = clock.instant().plus(java.time.Duration.ofHours(24))
        users.createInvitation(RegistrationInvitation(token.tokenHash, inviter.id, inviter.resourceOwnerId, expiresAt))
        record("auth.invitation.created", ActivityStatus.SUCCEEDED, "activity.auth.invitationCreated", inviter.id)
        return CreatedInvitation(token.rawToken, expiresAt)
    }

    @Transactional
    fun register(username: String, password: String, invitationCode: String, email: String? = null, emailProof: String? = null): AuthenticatedOwner {
        val normalized = normalizeUsername(username)
        registrationAttempts.backoffFor(normalized)?.let { throw LoginRateLimitedException(it.retryAfter(clock.instant())) }
        val now = clock.instant()
        val account = UserAccount(UUID.randomUUID(), normalized, passwords.hash(password), true, now, now)
        val created = users.registerVerified(account, invitationTokens.hash(invitationCode), now, email, emailProof) ?: run {
            registrationAttempts.recordFailure(normalized)
            throw InvalidInvitationException()
        }
        registrationAttempts.recordSuccess(normalized)
        rbac?.initializeUser(created.id, created.resourceOwnerId, false)
        record("auth.user.registered", ActivityStatus.SUCCEEDED, "activity.auth.userRegistered", created.id)
        return AuthenticatedOwner(created, sessions.create(created.id))
    }

    @Transactional
    fun setup(username: String, password: String, setupSecret: String? = null, spaceType: SpaceType = SpaceType.HOME, spaceName: String = "Kyrion"): AuthenticatedOwner {
        if (users.setupCompleted()) throw SetupAlreadyCompletedException()
        (bootstrap ?: throw BootstrapForbiddenException()).verify(setupSecret)
        val normalized = normalizeUsername(username)
        val now = clock.instant()
        val account = UserAccount(UUID.randomUUID(), normalized, passwords.hash(password), true, now, now)
        val created = users.createOwner(account) ?: throw SetupAlreadyCompletedException()
        rbac?.initializeUser(created.id, created.id, true)
        spaces?.update(created.id, SpaceSettingsRequest(spaceName, spaceType))
        record("auth.owner.setup", ActivityStatus.SUCCEEDED, "activity.auth.ownerSetup", created.id)
        return AuthenticatedOwner(created, sessions.create(created.id))
    }

    fun login(username: String, password: String): AuthenticatedOwner {
        val normalized = normalizeUsername(username)
        loginAttempts.backoffFor(normalized)?.let { backoff ->
            record("auth.login", ActivityStatus.DENIED, "activity.auth.loginRateLimited")
            throw LoginRateLimitedException(backoff.retryAfter(clock.instant()))
        }
        val account = users.findByUsername(normalized)
        if (account == null || !account.enabled || !passwords.matches(password, account.passwordHash)) {
            record("auth.login", ActivityStatus.DENIED, "activity.auth.loginFailed")
            loginAttempts.recordFailure(normalized)
            throw InvalidCredentialsException()
        }
        boundary?.actor(account.id)
        loginAttempts.recordSuccess(normalized)
        record("auth.login", ActivityStatus.SUCCEEDED, "activity.auth.loginSucceeded", account.id)
        return AuthenticatedOwner(account, sessions.create(account.id))
    }

    fun authenticate(rawToken: String): UserAccount? {
        return authenticatedSession(rawToken)?.first
    }

    fun activeSessions(rawToken: String): List<ActiveSession> {
        val (user, current) = authenticatedSession(rawToken) ?: throw UnauthenticatedException()
        return sessions.activeForUser(user.id).map { session ->
            ActiveSession(session.id, session.createdAt, session.lastSeenAt, session.expiresAt, session.id == current.id)
        }
    }

    fun revokeSession(rawToken: String, sessionId: UUID) {
        val (user, current) = authenticatedSession(rawToken) ?: throw UnauthenticatedException()
        if (sessionId == current.id) throw CurrentSessionRevocationException()
        if (!sessions.revokeForUser(user.id, sessionId)) throw AuthSessionNotFoundException()
        record("auth.session.revoke", ActivityStatus.SUCCEEDED, "activity.auth.sessionRevoked", user.id)
    }

    fun logout(rawToken: String, actorId: UUID?): Boolean = sessions.revoke(rawToken).also { revoked ->
        if (revoked) record("auth.logout", ActivityStatus.SUCCEEDED, "activity.auth.logout", actorId)
    }

    @Transactional
    fun changePassword(rawToken: String, currentPassword: String, newPassword: String): AuthenticatedOwner {
        val initial = authenticatedSession(rawToken, touch = false)?.first ?: throw UnauthenticatedException()
        rbac?.lockIdentity(initial.id)
        val account = authenticatedSession(rawToken, touch = false)?.first ?: throw UnauthenticatedException()
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

    private fun authenticatedSession(rawToken: String, touch: Boolean = true): Pair<UserAccount, AuthSession>? {
        val session = sessions.authenticate(rawToken, touch) ?: return null
        val user = users.findById(session.userId)?.takeIf { it.enabled } ?: return null
        boundary?.let { check -> if (runCatching { check.actor(user.id) }.isFailure) return null }
        return user to session
    }

    private fun record(type: String, status: ActivityStatus, summary: String, actorId: UUID? = null) {
        activity.record(
            category = ActivityCategory.SECURITY,
            eventType = type,
            status = status,
            actorType = actorId?.let { ActivityActorType.USER } ?: ActivityActorType.SYSTEM,
            actorId = actorId?.toString(),
            source = "kyrion-core",
            summaryCode = summary,
            ownerId = actorId?.let { users.findById(it)?.resourceOwnerId },
        )
    }
}

class SetupAlreadyCompletedException : RuntimeException()
class UsernameTakenException : RuntimeException()
class InvalidInvitationException : RuntimeException()
class InvitationForbiddenException : RuntimeException()
class InvalidCredentialsException : RuntimeException()
class InvalidCurrentPasswordException : RuntimeException()
class PasswordUnchangedException : RuntimeException()
class AuthSessionNotFoundException : RuntimeException()
class CurrentSessionRevocationException : RuntimeException()

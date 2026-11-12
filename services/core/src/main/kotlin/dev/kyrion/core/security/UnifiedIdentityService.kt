package dev.kyrion.core.security

import dev.kyrion.core.activity.*
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Service
import org.springframework.transaction.support.TransactionTemplate
import java.sql.Timestamp
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.util.UUID

class CentralIdentityException(val code: String) : RuntimeException()
@com.fasterxml.jackson.annotation.JsonInclude(com.fasterxml.jackson.annotation.JsonInclude.Include.NON_NULL)
data class CentralLinkStatus(val linked: Boolean, val issuer: String? = null)
data class CentralDeviceStart(val operationToken: String, val userCode: String, val verificationUri: String, val expiresAt: Instant, val interval: Long)
data class CentralPollStatus(val status: String)

/** The device secret exists only in bounded process memory. Restart abandons pending operations. */
@Service
class UnifiedIdentityService(
    private val provider: CentralIdentityProvider,
    private val authentication: LocalAuthenticationService,
    private val users: UserAccountRepository,
    private val sessions: AuthSessionService,
    private val passwords: PasswordHashingService,
    private val rbac: RbacService,
    private val jdbc: JdbcClient,
    private val activity: ActivityService,
    private val transactions: TransactionTemplate,
    private val clock: Clock = Clock.systemUTC(),
    private val bootstrap: FirstOwnerBootstrap? = null,
) {
    private data class Operation(
        val deviceCode: String,
        val user: UUID?,
        val localSession: String?,
        val expiresAt: Instant,
        var interval: Long,
        var nextPoll: Instant,
        var identity: ConfirmedCentralIdentity? = null,
        @Volatile var consumed: Boolean = false,
        val setupBootstrapHash: String? = null,
    )
    private val tokens = SessionTokenService()
    private val operations = LinkedHashMap<String, Operation>()
    private val reauthenticationAttempts = LoginAttemptLimiter(clock)
    private val starts = java.util.ArrayDeque<Instant>()

    fun available() = provider.available()

    fun startSetup(setupSecret: String?): CentralDeviceStart {
        verifySetupSecret(setupSecret)
        val started = start("LOGIN", null, null)
        synchronized(operations) {
            val key = tokens.hash(started.operationToken)
            operations[key] = operations.getValue(key).copy(setupBootstrapHash = tokens.hash(setupSecret!!))
        }
        return started
    }

    fun pollSetup(operationToken: String, setupSecret: String?): CentralPollStatus {
        verifySetupSecret(setupSecret)
        if (operation(operationToken).setupBootstrapHash == null) fail("CENTRAL_OPERATION_INVALID")
        return poll(operationToken, setupSecret)
    }

    fun cancelSetup(operationToken: String, setupSecret: String?) {
        verifySetupSecret(setupSecret)
        if (operation(operationToken).setupBootstrapHash == null) fail("CENTRAL_OPERATION_INVALID")
        cancel(operationToken, setupSecret)
    }

    fun completeSetup(
        operationToken: String,
        setupSecret: String?,
        credentials: CredentialsRequest,
        confirm: Boolean
    ): AuthenticatedOwner {
        verifySetupSecret(setupSecret)
        val operation = operation(operationToken)
        synchronized(operation) {
            verify(operation, setupSecret)
            if (operation.setupBootstrapHash == null || !confirm) fail("CENTRAL_OPERATION_INVALID")
            val identity = operation.identity ?: fail("CENTRAL_OPERATION_PENDING")
            if (!identity.expiresAt.isAfter(clock.instant())) fail("CENTRAL_OPERATION_INVALID")
            operation.consumed = true
            return transactions.execute {
                jdbc.sql("SELECT pg_advisory_xact_lock(5544332211)").query { _, _ -> true }.single()
                if (!operation.expiresAt.isAfter(clock.instant()) || !identity.expiresAt.isAfter(clock.instant())) fail(
                    "CENTRAL_OPERATION_INVALID"
                )
                val owner = authentication.setup(
                    credentials.username,
                    credentials.password,
                    setupSecret,
                    credentials.spaceType ?: SpaceType.HOME,
                    credentials.spaceName ?: "Kyrion"
                )
                val inserted = jdbc.sql(
                    """INSERT INTO central_identity_link(user_id,issuer,subject,linked_at)
                    VALUES(:user,:issuer,:subject,:now) ON CONFLICT DO NOTHING"""
                )
                    .param("user", owner.user.id).param("issuer", identity.issuer).param("subject", identity.subject)
                    .param("now", Timestamp.from(clock.instant())).update()
                if (inserted != 1) fail("CENTRAL_IDENTITY_ALREADY_LINKED")
                audit("identity.central.linked", owner.user)
                owner
            } ?: fail("CENTRAL_OPERATION_INVALID")
        }
    }

    private fun verifySetupSecret(secret: String?) {
        if (!authentication.setupRequired()) throw SetupAlreadyCompletedException()
        (bootstrap ?: throw BootstrapForbiddenException()).verify(secret)
    }

    @org.springframework.scheduling.annotation.Scheduled(fixedDelay = 60_000)
    fun expireOperations() = synchronized(operations) {
        operations.entries.removeIf { !it.value.expiresAt.isAfter(clock.instant()) || it.value.consumed }
        Unit
    }

    fun status(rawSession: String): CentralLinkStatus {
        val user = current(rawSession)
        return jdbc.sql("SELECT issuer FROM central_identity_link WHERE user_id=:user").param("user", user.id)
            .query(String::class.java).optional().orElse(null)?.let { CentralLinkStatus(true, it) } ?: CentralLinkStatus(false)
    }

    fun start(mode: String, rawSession: String?, currentPassword: String?): CentralDeviceStart {
        if (mode !in setOf("LOGIN", "LINK")) fail("CENTRAL_OPERATION_INVALID")
        val user = if (mode == "LINK") current(rawSession) else null
        if (user != null) reauthenticate(user, currentPassword ?: "")
        // Bound unauthenticated upstream work and memory independently of account existence.
        synchronized(operations) {
            operations.entries.removeIf { !it.value.expiresAt.isAfter(clock.instant()) || it.value.consumed }
            if (operations.size >= 256) fail("CENTRAL_UNAVAILABLE")
            val now = clock.instant()
            while (starts.peekFirst()?.isBefore(now.minusSeconds(60)) == true) starts.removeFirst()
            if (starts.size >= 30) throw LoginRateLimitedException(Duration.ofSeconds(60))
            starts.addLast(now)
        }
        val device = provider.startDevice()
        val token = tokens.create()
        val now = clock.instant()
        val expiry = now.plusSeconds(device.expiresIn.coerceIn(1, 600))
        val interval = device.interval.coerceIn(1, 60)
        synchronized(operations) {
            if (operations.size >= 256) fail("CENTRAL_UNAVAILABLE")
            operations[token.tokenHash] = Operation(device.deviceCode, user?.id, rawSession?.takeIf { user != null }?.let(tokens::hash), expiry, interval, now.plusSeconds(interval))
        }
        return CentralDeviceStart(token.rawToken, device.userCode, device.verificationUri, expiry, interval)
    }

    fun poll(operationToken: String, rawSession: String?): CentralPollStatus {
        val operation = operation(operationToken)
        synchronized(operation) {
            verify(operation, rawSession)
            operation.identity?.let { return CentralPollStatus("CONFIRM") }
            val now = clock.instant()
            if (operation.nextPoll.isAfter(now)) return CentralPollStatus("PENDING")
            operation.nextPoll = now.plusSeconds(operation.interval)
            val identity = try { provider.pollDevice(operation.deviceCode) } catch (error: CentralIdentityException) {
                if (error.code == "CENTRAL_SLOW_DOWN") {
                    operation.interval = (operation.interval + 5).coerceAtMost(120)
                    operation.nextPoll = now.plusSeconds(operation.interval)
                    return CentralPollStatus("PENDING")
                }
                if (error.code in setOf("CENTRAL_DENIED", "CENTRAL_INVALID_RESPONSE")) operation.consumed = true
                throw error
            }
            if (identity != null) {
                if (!identity.expiresAt.isAfter(now)) fail("CENTRAL_OPERATION_INVALID")
                operation.identity = identity
            }
            return CentralPollStatus(if (identity == null) "PENDING" else "CONFIRM")
        }
    }

    /** Confirmation is one-use even if the transaction fails; a fresh proof is then required. */
    fun complete(operationToken: String, rawSession: String?, confirm: Boolean): AuthenticatedOwner? {
        val operation = operation(operationToken)
        synchronized(operation) {
            if (operation.setupBootstrapHash != null) fail("CENTRAL_OPERATION_INVALID")
            verify(operation, rawSession)
            if (!confirm) fail("CENTRAL_OPERATION_INVALID")
            val identity = operation.identity ?: fail("CENTRAL_OPERATION_PENDING")
            if (!identity.expiresAt.isAfter(clock.instant())) fail("CENTRAL_OPERATION_INVALID")
            operation.consumed = true
            return transactions.execute {
                // Shared advisory lock serializes link/login/unlink across Core processes.
                jdbc.sql("SELECT pg_advisory_xact_lock(5544332211)").query { _, _ -> true }.single()
                fun requireFreshProof() {
                    if (!operation.expiresAt.isAfter(clock.instant()) || !identity.expiresAt.isAfter(clock.instant())) fail("CENTRAL_OPERATION_INVALID")
                }
                if (operation.user != null) {
                    rbac.lockIdentity(operation.user)
                    val user = current(rawSession)
                    requireFreshProof()
                    if (current(rawSession).id != operation.user) fail("CENTRAL_OPERATION_INVALID")
                    val inserted = jdbc.sql("""INSERT INTO central_identity_link(user_id,issuer,subject,linked_at)
                        VALUES(:user,:issuer,:subject,:now) ON CONFLICT DO NOTHING""")
                        .param("user", user.id).param("issuer", identity.issuer).param("subject", identity.subject)
                        .param("now", Timestamp.from(clock.instant())).update()
                    if (inserted != 1) fail("CENTRAL_IDENTITY_ALREADY_LINKED")
                    audit("identity.central.linked", user)
                    null
                } else {
                    val id = jdbc.sql("SELECT user_id FROM central_identity_link WHERE issuer=:issuer AND subject=:subject")
                        .param("issuer", identity.issuer).param("subject", identity.subject).query(UUID::class.java).optional().orElse(null)
                        ?: fail("SPACE_ACCESS_REQUIRED")
                    rbac.lockIdentity(id)
                    requireFreshProof()
                    val user = users.findById(id)?.takeIf { it.enabled } ?: fail("SPACE_ACCESS_REQUIRED")
                    val lifetime = Duration.between(clock.instant(), identity.expiresAt).coerceAtMost(Duration.ofMinutes(15))
                    if (lifetime.isNegative || lifetime.isZero) fail("CENTRAL_OPERATION_INVALID")
                    val session = sessions.create(user.id, lifetime)
                    jdbc.sql("INSERT INTO central_auth_session(session_id,user_id) VALUES(:session,:user)")
                        .param("session", session.session.id).param("user", user.id).update()
                    audit("auth.central.login", user)
                    AuthenticatedOwner(user, session)
                }
            }
        }
    }

    fun cancel(operationToken: String, rawSession: String?) {
        val operation = operation(operationToken)
        synchronized(operation) { verify(operation, rawSession); operation.consumed = true }
    }

    fun unlink(rawSession: String, currentPassword: String) {
        val initial = current(rawSession)
        reauthenticate(initial, currentPassword)
        transactions.executeWithoutResult {
            jdbc.sql("SELECT pg_advisory_xact_lock(5544332211)").query { _, _ -> true }.single()
            rbac.lockIdentity(initial.id)
            val user = current(rawSession)
            // Recheck the proof against the locked current credential, not a stale snapshot.
            reauthenticate(user, currentPassword)
            // Every supported local user retains an Argon2id credential. Never remove it here.
            if (user.passwordHash.isBlank()) fail("LOCAL_LOGIN_REQUIRED")
            jdbc.sql("""UPDATE auth_session SET revoked_at=:now WHERE id IN
                (SELECT session_id FROM central_auth_session WHERE user_id=:user) AND revoked_at IS NULL""")
                .param("now", Timestamp.from(clock.instant())).param("user", user.id).update()
            jdbc.sql("DELETE FROM central_identity_link WHERE user_id=:user").param("user", user.id).update()
            audit("identity.central.unlinked", user)
        }
    }

    private fun reauthenticate(user: UserAccount, password: String) {
        val key = user.id.toString()
        reauthenticationAttempts.backoffFor(key)?.let { throw LoginRateLimitedException(it.retryAfter(clock.instant())) }
        if (!passwords.matches(password, user.passwordHash)) {
            reauthenticationAttempts.recordFailure(key)
            activity.record(ActivityCategory.SECURITY, "identity.central.reauthentication", ActivityStatus.DENIED,
                ActivityActorType.USER, "kyrion-core", "identity.central.reauthenticationFailed", user.id.toString(), ownerId = user.resourceOwnerId)
            throw InvalidCurrentPasswordException()
        }
        reauthenticationAttempts.recordSuccess(key)
    }

    private fun current(rawSession: String?) = rawSession?.let(authentication::authenticate) ?: throw UnauthenticatedException()
    private fun operation(token: String): Operation = synchronized(operations) {
        operations[tokens.hash(token)] ?: fail("CENTRAL_OPERATION_INVALID")
    }
    private fun verify(operation: Operation, rawSession: String?) {
        if (operation.consumed || !operation.expiresAt.isAfter(clock.instant())) fail("CENTRAL_OPERATION_INVALID")
        if (operation.setupBootstrapHash != null && (rawSession == null || tokens.hash(rawSession) != operation.setupBootstrapHash))
            fail("CENTRAL_OPERATION_INVALID")
        if (operation.user != null && (rawSession == null || tokens.hash(rawSession) != operation.localSession || current(rawSession).id != operation.user))
            fail("CENTRAL_OPERATION_INVALID")
    }
    private fun audit(type: String, user: UserAccount) = activity.record(ActivityCategory.SECURITY, type, ActivityStatus.SUCCEEDED,
        ActivityActorType.USER, "kyrion-core", type, user.id.toString(), ownerId = user.resourceOwnerId)
    private fun fail(code: String): Nothing = throw CentralIdentityException(code)
}

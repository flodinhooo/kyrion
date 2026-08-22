package dev.kyrion.core.security

import java.time.Clock
import java.time.Duration
import java.time.Instant
import kotlin.math.min

data class LoginBackoff(val retryAt: Instant) {
    fun retryAfter(now: Instant): Duration = Duration.between(now, retryAt).coerceAtLeast(Duration.ofSeconds(1))
}

class LoginAttemptLimiter(
    private val clock: Clock = Clock.systemUTC(),
    private val failuresBeforeBackoff: Int = 5,
    private val initialBackoff: Duration = Duration.ofSeconds(30),
    private val maximumBackoff: Duration = Duration.ofMinutes(15),
    private val maximumTrackedAccounts: Int = 10_000,
) {
    private data class AttemptState(val failures: Int, val retryAt: Instant?)

    private val attempts = LinkedHashMap<String, AttemptState>()

    @Synchronized
    fun backoffFor(normalizedUsername: String): LoginBackoff? {
        val now = clock.instant()
        val state = attempts[normalizedUsername] ?: return null
        val retryAt = state.retryAt ?: return null
        return if (retryAt.isAfter(now)) LoginBackoff(retryAt) else null
    }

    @Synchronized
    fun recordFailure(normalizedUsername: String): LoginBackoff? {
        val now = clock.instant()
        val previous = attempts[normalizedUsername]
        val failures = (previous?.failures ?: 0) + 1
        val retryAt = if (failures >= failuresBeforeBackoff) now.plus(backoffDuration(failures)) else null
        attempts[normalizedUsername] = AttemptState(failures, retryAt)
        trimToBound()
        return retryAt?.let(::LoginBackoff)
    }

    @Synchronized
    fun recordSuccess(normalizedUsername: String) {
        attempts.remove(normalizedUsername)
    }

    private fun backoffDuration(failures: Int): Duration {
        val exponent = min(failures - failuresBeforeBackoff, 20)
        val multiplier = 1L shl exponent
        val seconds = min(initialBackoff.seconds * multiplier, maximumBackoff.seconds)
        return Duration.ofSeconds(seconds)
    }

    private fun trimToBound() {
        while (attempts.size > maximumTrackedAccounts) {
            attempts.remove(attempts.keys.first())
        }
    }
}

class LoginRateLimitedException(val retryAfter: Duration) : RuntimeException()

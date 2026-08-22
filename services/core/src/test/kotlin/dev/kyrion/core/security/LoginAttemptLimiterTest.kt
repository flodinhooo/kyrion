package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import java.time.Duration
import java.time.Clock
import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset

class LoginAttemptLimiterTest {
    @Test
    fun `increases temporary backoff up to the configured maximum`() {
        val clock = MutableLoginClock(Instant.parse("2026-08-22T12:00:00Z"))
        val limiter = LoginAttemptLimiter(clock)

        repeat(4) { assertThat(limiter.recordFailure("flo")).isNull() }
        assertThat(limiter.recordFailure("flo")?.retryAfter(clock.instant())).isEqualTo(Duration.ofSeconds(30))
        clock.advance(Duration.ofSeconds(30))
        assertThat(limiter.recordFailure("flo")?.retryAfter(clock.instant())).isEqualTo(Duration.ofMinutes(1))

        repeat(10) {
            clock.advance(Duration.ofMinutes(15))
            limiter.recordFailure("flo")
        }
        assertThat(limiter.backoffFor("flo")?.retryAfter(clock.instant())).isEqualTo(Duration.ofMinutes(15))
    }

    @Test
    fun `rate limited response exposes stable code and retry header`() {
        val response = AuthenticationErrorHandler().loginRateLimited(LoginRateLimitedException(Duration.ofSeconds(30)))

        assertThat(response.statusCode.value()).isEqualTo(429)
        assertThat(response.headers.getFirst("Retry-After")).isEqualTo("30")
        assertThat(response.body?.code).isEqualTo("LOGIN_RATE_LIMITED")
    }
}

private class MutableLoginClock(private var current: Instant) : Clock() {
    override fun getZone() = ZoneOffset.UTC
    override fun withZone(zone: ZoneId): Clock = this
    override fun instant(): Instant = current
    fun advance(duration: Duration) { current = current.plus(duration) }
}

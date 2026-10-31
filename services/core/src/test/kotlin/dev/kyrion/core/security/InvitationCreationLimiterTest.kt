package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset
import java.util.UUID

class InvitationCreationLimiterTest {
    @Test
    fun `issuance is bounded per actor and resets after the window`() {
        val clock = MutableClock(Instant.parse("2026-10-30T12:00:00Z"))
        val limiter = InvitationCreationLimiter(clock)
        val actor = UUID.randomUUID()
        repeat(20) { limiter.check(actor) }
        assertThatThrownBy { limiter.check(actor) }.isInstanceOf(LoginRateLimitedException::class.java)
        limiter.check(UUID.randomUUID())
        clock.now = clock.now.plusSeconds(60)
        limiter.check(actor)
    }

    private class MutableClock(var now: Instant) : Clock() {
        override fun instant(): Instant = now
        override fun getZone(): ZoneId = ZoneOffset.UTC
        override fun withZone(zone: ZoneId): Clock = this
    }
}

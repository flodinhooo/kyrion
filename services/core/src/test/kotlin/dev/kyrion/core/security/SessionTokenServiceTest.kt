package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class SessionTokenServiceTest {
    private val service = SessionTokenService()

    @Test
    fun `creates an opaque token and stores only its deterministic hash`() {
        val token = service.create()

        assertThat(token.rawToken).hasSize(43)
        assertThat(token.tokenHash).hasSize(64)
        assertThat(token.tokenHash).isNotEqualTo(token.rawToken)
        assertThat(service.hash(token.rawToken)).isEqualTo(token.tokenHash)
    }

    @Test
    fun `creates a unique token for every session`() {
        val first = service.create()
        val second = service.create()

        assertThat(second.rawToken).isNotEqualTo(first.rawToken)
        assertThat(second.tokenHash).isNotEqualTo(first.tokenHash)
    }
}

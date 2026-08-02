package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class PasswordHashingServiceTest {
    private val service = PasswordHashingService()

    @Test
    fun `hashes passwords with argon2id and a unique salt`() {
        val firstHash = service.hash("correct horse battery staple")
        val secondHash = service.hash("correct horse battery staple")

        assertThat(firstHash).startsWith("\$argon2id\$")
        assertThat(secondHash).isNotEqualTo(firstHash)
        assertThat(service.matches("correct horse battery staple", firstHash)).isTrue()
        assertThat(service.matches("wrong password", firstHash)).isFalse()
    }
}

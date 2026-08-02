package dev.kyrion.core.security

import org.springframework.security.crypto.argon2.Argon2PasswordEncoder
import org.springframework.stereotype.Component

@Component
class PasswordHashingService {
    private val encoder = Argon2PasswordEncoder(
        SALT_LENGTH_BYTES,
        HASH_LENGTH_BYTES,
        PARALLELISM,
        MEMORY_KIB,
        ITERATIONS,
    )

    fun hash(password: CharSequence): String {
        require(password.isNotEmpty()) { "Password must not be empty" }
        return encoder.encode(password)
    }

    fun matches(password: CharSequence, encodedPassword: String): Boolean =
        encoder.matches(password, encodedPassword)

    private companion object {
        const val SALT_LENGTH_BYTES = 16
        const val HASH_LENGTH_BYTES = 32
        const val PARALLELISM = 1
        const val MEMORY_KIB = 19 * 1024
        const val ITERATIONS = 2
    }
}

package dev.kyrion.core.security

import org.springframework.stereotype.Component
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import java.util.HexFormat

data class SessionToken(
    val rawToken: String,
    val tokenHash: String,
)

@Component
class SessionTokenService(
    private val secureRandom: SecureRandom = SecureRandom(),
) {
    fun create(): SessionToken {
        val bytes = ByteArray(TOKEN_LENGTH_BYTES)
        secureRandom.nextBytes(bytes)
        val rawToken = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
        return SessionToken(rawToken = rawToken, tokenHash = hash(rawToken))
    }

    fun hash(rawToken: String): String {
        require(rawToken.isNotEmpty()) { "Session token must not be empty" }
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(rawToken.toByteArray(StandardCharsets.UTF_8))
        return HexFormat.of().formatHex(digest)
    }

    private companion object {
        const val TOKEN_LENGTH_BYTES = 32
    }
}

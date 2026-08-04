package dev.kyrion.core.integration

import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardOpenOption
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

data class ProtectedCredential(val ciphertext: ByteArray, val nonce: ByteArray, val version: Int = 1)

@Component
class CredentialCipher(
    @Value("\${kyrion.credentials.key-file:E:/Kyrion/Data/secrets/credential.key}") private val keyFile: String,
) {
    private val random = SecureRandom()
    private val key by lazy { SecretKeySpec(loadOrCreateKey(), "AES") }

    fun protect(value: String, context: String): ProtectedCredential {
        val nonce = ByteArray(12).also(random::nextBytes)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(128, nonce))
        cipher.updateAAD(context.toByteArray())
        return ProtectedCredential(cipher.doFinal(value.toByteArray()), nonce)
    }

    fun reveal(value: IntegrationConnection): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, value.credentialNonce))
        cipher.updateAAD("${value.ownerId}:${value.id}:${value.provider}".toByteArray())
        return String(cipher.doFinal(value.credentialCiphertext))
    }

    private fun loadOrCreateKey(): ByteArray {
        val path = Path.of(keyFile).toAbsolutePath().normalize()
        Files.createDirectories(path.parent)
        if (Files.exists(path)) return Files.readAllBytes(path).also { require(it.size == 32) { "Credential key must be 32 bytes" } }
        val generated = ByteArray(32).also(random::nextBytes)
        Files.write(path, generated, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)
        return generated
    }
}

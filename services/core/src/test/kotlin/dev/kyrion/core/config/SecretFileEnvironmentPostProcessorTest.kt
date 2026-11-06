package dev.kyrion.core.config

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path

class SecretFileEnvironmentPostProcessorTest {
    @TempDir
    lateinit var directory: Path

    @Test
    fun `database password is read without interpreting binary key paths`() {
        val password = directory.resolve("password")
        Files.writeString(password, "test-password\r\n")
        val binary = directory.resolve("key")
        Files.write(binary, byteArrayOf(0xff.toByte(), 0xfe.toByte(), 0))
        assertEquals(
            mapOf("KYRION_DATABASE_PASSWORD" to "test-password"),
            resolveSecretFiles(
                mapOf(
                    "KYRION_DATABASE_PASSWORD_FILE" to password.toString(),
                    "KYRION_CREDENTIAL_KEY_FILE" to binary.toString(),
                    "KYRION_AUDIT_INTEGRITY_KEY_FILE" to binary.toString(),
                    "KYRION_BOOTSTRAP_SECRET_FILE" to directory.resolve("absent-bootstrap").toString(),
                    "UNRELATED_FILE" to directory.resolve("absent").toString(),
                )
            ),
        )
    }

    @Test
    fun `missing and empty database secret paths fail closed`() {
        for (path in listOf("", directory.resolve("missing").toString(), directory.toString())) {
            assertThrows(IllegalArgumentException::class.java) {
                resolveSecretFiles(mapOf("KYRION_DATABASE_PASSWORD_FILE" to path))
            }
        }
    }
}

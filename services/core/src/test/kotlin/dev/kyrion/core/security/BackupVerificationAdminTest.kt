package dev.kyrion.core.security

import org.junit.jupiter.api.Assertions.assertDoesNotThrow
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Test

class BackupVerificationAdminTest {
    private val database = "kyrion_verify_0123456789abcdef0123456789abcdef"

    @Test
    fun `only generated verification targets on literal loopback are accepted`() {
        assertDoesNotThrow { BackupVerificationAdmin.validateTarget("jdbc:postgresql://127.0.0.1:15432/$database") }
        listOf(
            "jdbc:postgresql://127.0.0.1:5432/kyrion",
            "jdbc:postgresql://localhost:5432/$database",
            "jdbc:postgresql://192.168.1.1:5432/$database",
            "jdbc:postgresql://127.0.0.1:5432/$database?options=-c%20search_path=unsafe",
            "jdbc:postgresql://127.0.0.1:99999/$database",
            "jdbc:postgresql://127.0.0.1:1023/$database",
            "jdbc:postgresql://127.0.0.1:5432/${database.uppercase()}",
        ).forEach { url -> assertThrows(IllegalArgumentException::class.java) { BackupVerificationAdmin.validateTarget(url) } }
    }
}

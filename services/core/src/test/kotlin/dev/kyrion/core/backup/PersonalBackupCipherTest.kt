package dev.kyrion.core.backup

import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import java.time.Instant
import java.util.UUID

class PersonalBackupCipherTest {
    @Test
    fun `encrypted portable backup round trips and rejects wrong passphrase`() {
        val cipher = PersonalBackupCipher()
        val payload = PersonalBackupPayload(
            1, Instant.parse("2026-08-22T15:00:00Z"),
            listOf(BackupConversation(UUID.randomUUID(), "Private", Instant.EPOCH, Instant.EPOCH,
                listOf(BackupMessage(UUID.randomUUID(), "user", "secret text", 0, Instant.EPOCH)))),
            true, emptyList(), mapOf("conversations" to "keep_forever"),
        )
        val envelope = cipher.encrypt(payload, "a-strong-backup-passphrase")

        assertThat(envelope.ciphertext).doesNotContain("secret text")
        assertThat(cipher.decrypt(envelope, "a-strong-backup-passphrase")).isEqualTo(payload)
        assertThatThrownBy { cipher.decrypt(envelope, "definitely-wrong-passphrase") }
            .isInstanceOf(javax.crypto.AEADBadTagException::class.java)
    }
}

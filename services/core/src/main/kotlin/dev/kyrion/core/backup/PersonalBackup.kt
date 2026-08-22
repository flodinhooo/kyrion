package dev.kyrion.core.backup

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import dev.kyrion.core.security.UnauthenticatedException
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.Size
import org.springframework.http.HttpHeaders
import org.springframework.http.ResponseEntity
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController
import java.security.SecureRandom
import java.time.Clock
import java.time.Instant
import java.util.Base64
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

data class PersonalBackupRequest(@field:Size(min = 12, max = 200) val passphrase: String)
data class EncryptedBackupEnvelope(
    val format: String = FORMAT, val formatVersion: Int = 1, val algorithm: String = "AES-256-GCM",
    val kdf: String = "PBKDF2-HMAC-SHA256", val iterations: Int = ITERATIONS,
    val salt: String, val nonce: String, val ciphertext: String,
)
data class BackupConversation(val id: UUID, val title: String, val createdAt: Instant, val updatedAt: Instant, val messages: List<BackupMessage>)
data class BackupMessage(val id: UUID, val role: String, val content: String, val position: Int, val createdAt: Instant)
data class BackupMemory(val id: UUID, val category: String, val content: String, val sensitivity: String, val status: String, val createdAt: Instant, val updatedAt: Instant, val confirmedAt: Instant?)
data class PersonalBackupPayload(
    val formatVersion: Int, val createdAt: Instant, val conversations: List<BackupConversation>,
    val memoryEnabled: Boolean, val memories: List<BackupMemory>, val retention: Map<String, String>,
    val excluded: List<String> = listOf("authentication", "sessions", "integrationCredentials", "deviceTokens", "privateKeys"),
)

const val FORMAT = "kyrion-personal-backup"
const val ITERATIONS = 600_000

class PersonalBackupCipher(
    private val mapper: ObjectMapper = jacksonObjectMapper().findAndRegisterModules(),
    private val random: SecureRandom = SecureRandom(),
) {
    fun encrypt(payload: PersonalBackupPayload, passphrase: String): EncryptedBackupEnvelope {
        val salt = ByteArray(16).also(random::nextBytes)
        val nonce = ByteArray(12).also(random::nextBytes)
        val key = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
            .generateSecret(PBEKeySpec(passphrase.toCharArray(), salt, ITERATIONS, 256)).encoded
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
        cipher.updateAAD("$FORMAT:1".toByteArray())
        val encrypted = cipher.doFinal(mapper.writeValueAsBytes(payload))
        key.fill(0)
        return EncryptedBackupEnvelope(salt = salt.b64(), nonce = nonce.b64(), ciphertext = encrypted.b64())
    }
    fun decrypt(envelope: EncryptedBackupEnvelope, passphrase: String): PersonalBackupPayload {
        require(envelope.format == FORMAT && envelope.formatVersion == 1 && envelope.iterations == ITERATIONS)
        val decoder = Base64.getDecoder()
        val salt = decoder.decode(envelope.salt); val nonce = decoder.decode(envelope.nonce)
        val key = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
            .generateSecret(PBEKeySpec(passphrase.toCharArray(), salt, ITERATIONS, 256)).encoded
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
        cipher.updateAAD("$FORMAT:1".toByteArray())
        val plain = cipher.doFinal(decoder.decode(envelope.ciphertext)); key.fill(0)
        return mapper.readValue(plain, PersonalBackupPayload::class.java)
    }
    private fun ByteArray.b64() = Base64.getEncoder().encodeToString(this)
}

@RestController
@RequestMapping("/v1/backups")
class PersonalBackupController(
    private val jdbc: JdbcClient,
    private val clock: Clock = Clock.systemUTC(),
    private val cipher: PersonalBackupCipher = PersonalBackupCipher(),
) {
    @PostMapping("/personal")
    fun export(@Valid @RequestBody body: PersonalBackupRequest, request: HttpServletRequest): ResponseEntity<EncryptedBackupEnvelope> {
        val ownerId = request.ownerId()
        val payload = PersonalBackupPayload(1, clock.instant(), conversations(ownerId), memoryEnabled(ownerId), memories(ownerId), retention(ownerId))
        val filename = "kyrion-personal-backup-${clock.instant().toString().take(10)}.json"
        return ResponseEntity.ok().header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"$filename\"").body(cipher.encrypt(payload, body.passphrase))
    }
    private fun conversations(ownerId: UUID) = jdbc.sql("SELECT id,title,created_at,updated_at FROM conversation WHERE owner_id=:ownerId ORDER BY created_at")
        .param("ownerId", ownerId).query { rs, _ ->
            val id=rs.getObject("id",UUID::class.java); BackupConversation(id,rs.getString("title"),rs.getTimestamp("created_at").toInstant(),rs.getTimestamp("updated_at").toInstant(),
                jdbc.sql("SELECT id,role,content,position,created_at FROM conversation_message WHERE conversation_id=:id ORDER BY position").param("id",id).query { m,_ -> BackupMessage(m.getObject("id",UUID::class.java),m.getString("role"),m.getString("content"),m.getInt("position"),m.getTimestamp("created_at").toInstant()) }.list())
        }.list()
    private fun memoryEnabled(ownerId: UUID) = jdbc.sql("SELECT enabled FROM owner_memory_settings WHERE owner_id=:id").param("id",ownerId).query(Boolean::class.java).optional().orElse(false)
    private fun memories(ownerId: UUID) = jdbc.sql("SELECT id,category,content,sensitivity,status,created_at,updated_at,confirmed_at FROM personal_memory WHERE owner_id=:id ORDER BY created_at")
        .param("id",ownerId).query { rs,_ -> BackupMemory(rs.getObject("id",UUID::class.java),rs.getString("category"),rs.getString("content"),rs.getString("sensitivity"),rs.getString("status"),rs.getTimestamp("created_at").toInstant(),rs.getTimestamp("updated_at").toInstant(),rs.getTimestamp("confirmed_at")?.toInstant()) }.list()
    private fun retention(ownerId: UUID): Map<String,String> = jdbc.sql("SELECT conversation_policy,activity_policy,personal_memory_policy FROM owner_retention_policy WHERE owner_id=:id").param("id",ownerId).query { rs,_ -> mapOf("conversations" to rs.getString(1),"activity" to rs.getString(2),"personalMemory" to rs.getString(3)) }.optional().orElse(mapOf("conversations" to "keep_forever","activity" to "keep_forever","personalMemory" to "keep_forever"))
    private fun HttpServletRequest.ownerId() = getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw UnauthenticatedException()
}

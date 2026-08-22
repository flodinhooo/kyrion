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
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.http.HttpStatus
import org.springframework.transaction.support.TransactionTemplate
import java.sql.Timestamp
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
data class PersonalBackupPreviewRequest(val envelope: EncryptedBackupEnvelope, @field:Size(min = 12, max = 200) val passphrase: String)
data class PersonalBackupPreview(
    val formatVersion: Int, val createdAt: String, val conversations: Int, val messages: Int,
    val memories: Int, val memoryEnabled: Boolean, val retention: Map<String, String>, val excluded: List<String>,
)
data class PersonalBackupImportRequest(
    val envelope: EncryptedBackupEnvelope, @field:Size(min = 12, max = 200) val passphrase: String,
    val confirmation: String,
)
data class PersonalBackupImportResult(val conversationsImported: Int, val conversationsSkipped: Int, val messagesImported: Int, val memoriesImported: Int, val memoriesSkipped: Int)
data class EncryptedBackupEnvelope(
    val format: String = FORMAT, val formatVersion: Int = 1, val algorithm: String = "AES-256-GCM",
    val kdf: String = "PBKDF2-HMAC-SHA256", val iterations: Int = ITERATIONS,
    val salt: String, val nonce: String, val ciphertext: String,
)
data class BackupConversation(val id: UUID, val title: String, val createdAt: String, val updatedAt: String, val messages: List<BackupMessage>)
data class BackupMessage(val id: UUID, val role: String, val content: String, val position: Int, val createdAt: String)
data class BackupMemory(
    val id: UUID, val category: String, val content: String, val sensitivity: String, val status: String,
    val createdAt: String, val updatedAt: String, val confirmedAt: String?,
    val sourceConversationId: UUID? = null, val sourceMessageId: UUID? = null, val conflictsWithMemoryId: UUID? = null,
)
data class PersonalBackupPayload(
    val formatVersion: Int, val createdAt: String, val conversations: List<BackupConversation>,
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
    private val transactions: TransactionTemplate,
    private val clock: Clock = Clock.systemUTC(),
    private val cipher: PersonalBackupCipher = PersonalBackupCipher(),
) {
    @PostMapping("/personal")
    fun export(@Valid @RequestBody body: PersonalBackupRequest, request: HttpServletRequest): ResponseEntity<EncryptedBackupEnvelope> {
        val ownerId = request.ownerId()
        val payload = PersonalBackupPayload(1, clock.instant().toString(), conversations(ownerId), memoryEnabled(ownerId), memories(ownerId), retention(ownerId))
        val filename = "kyrion-personal-backup-${clock.instant().toString().take(10)}.json"
        return ResponseEntity.ok().header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"$filename\"").body(cipher.encrypt(payload, body.passphrase))
    }
    @PostMapping("/personal/preview")
    fun preview(@Valid @RequestBody body: PersonalBackupPreviewRequest, request: HttpServletRequest): PersonalBackupPreview {
        request.ownerId()
        if (body.envelope.ciphertext.length > 70_000_000) throw PersonalBackupInvalidException()
        val payload = try { cipher.decrypt(body.envelope, body.passphrase) } catch (_: Exception) { throw PersonalBackupInvalidException() }
        if (payload.formatVersion != 1 || payload.conversations.size > 100_000 || payload.memories.size > 100_000) {
            throw PersonalBackupInvalidException()
        }
        return PersonalBackupPreview(
            payload.formatVersion, payload.createdAt, payload.conversations.size,
            payload.conversations.sumOf { it.messages.size }, payload.memories.size,
            payload.memoryEnabled, payload.retention, payload.excluded,
        )
    }
    @PostMapping("/personal/import")
    fun import(@Valid @RequestBody body: PersonalBackupImportRequest, request: HttpServletRequest): PersonalBackupImportResult {
        if (body.confirmation != "IMPORT") throw PersonalBackupConfirmationException()
        val ownerId=request.ownerId(); val payload=decryptAndValidate(body.envelope,body.passphrase); val now=clock.instant()
        return transactions.execute {
            var conversationsImported=0; var conversationsSkipped=0; var messagesImported=0; var memoriesImported=0; var memoriesSkipped=0
            val conversationIds=mutableMapOf<UUID,UUID>(); val messageIds=mutableMapOf<UUID,UUID>(); val memoryIds=mutableMapOf<UUID,UUID>()
            payload.conversations.forEach { source ->
                val existing=importTarget(ownerId,"conversation",source.id)
                if(existing!=null){conversationIds[source.id]=existing;conversationsSkipped++;return@forEach}
                validateConversation(source); val target=UUID.randomUUID();conversationIds[source.id]=target
                jdbc.sql("INSERT INTO conversation(id,owner_id,title,created_at,updated_at) VALUES(:id,:owner,:title,:created,:updated)")
                    .param("id",target).param("owner",ownerId).param("title",source.title).param("created",Timestamp.from(Instant.parse(source.createdAt))).param("updated",Timestamp.from(Instant.parse(source.updatedAt))).update()
                source.messages.sortedBy { it.position }.forEachIndexed { position,message ->
                    validateMessage(message); val messageTarget=UUID.randomUUID();messageIds[message.id]=messageTarget
                    jdbc.sql("INSERT INTO conversation_message(id,conversation_id,role,content,position,created_at) VALUES(:id,:conversation,:role,:content,:position,:created)")
                        .param("id",messageTarget).param("conversation",target).param("role",message.role).param("content",message.content).param("position",position).param("created",Timestamp.from(Instant.parse(message.createdAt))).update()
                    track(ownerId,"message",message.id,messageTarget,now);messagesImported++
                }
                track(ownerId,"conversation",source.id,target,now);conversationsImported++
            }
            payload.memories.forEach { source ->
                val existing=importTarget(ownerId,"memory",source.id)
                if(existing!=null){memoryIds[source.id]=existing;memoriesSkipped++}else{memoryIds[source.id]=UUID.randomUUID()}
            }
            payload.memories.forEach { source ->
                if(importTarget(ownerId,"memory",source.id)!=null)return@forEach
                validateMemory(source); val target=memoryIds.getValue(source.id)
                jdbc.sql("""INSERT INTO personal_memory(id,owner_id,category,content,sensitivity,origin,status,source_conversation_id,source_message_id,created_at,updated_at,confirmed_at,conflicts_with_memory_id)
                    VALUES(:id,:owner,:category,:content,:sensitivity,'explicit',:status,:conversation,:message,:created,:updated,:confirmed,:conflict)""")
                    .param("id",target).param("owner",ownerId).param("category",source.category).param("content",source.content).param("sensitivity",source.sensitivity).param("status",source.status)
                    .param("conversation",source.sourceConversationId?.let(conversationIds::get)).param("message",source.sourceMessageId?.let(messageIds::get))
                    .param("created",Timestamp.from(Instant.parse(source.createdAt))).param("updated",Timestamp.from(Instant.parse(source.updatedAt))).param("confirmed",source.confirmedAt?.let{Timestamp.from(Instant.parse(it))})
                    .param("conflict",source.conflictsWithMemoryId?.let(memoryIds::get)).update()
                track(ownerId,"memory",source.id,target,now);memoriesImported++
            }
            jdbc.sql("""INSERT INTO owner_memory_settings(owner_id,enabled,updated_at) VALUES(:id,:enabled,:now) ON CONFLICT(owner_id) DO UPDATE SET enabled=EXCLUDED.enabled,updated_at=EXCLUDED.updated_at""")
                .param("id",ownerId).param("enabled",payload.memoryEnabled).param("now",Timestamp.from(now)).update()
            PersonalBackupImportResult(conversationsImported,conversationsSkipped,messagesImported,memoriesImported,memoriesSkipped)
        }
    }
    private fun decryptAndValidate(envelope:EncryptedBackupEnvelope,passphrase:String):PersonalBackupPayload {
        val payload=try{cipher.decrypt(envelope,passphrase)}catch(_:Exception){throw PersonalBackupInvalidException()}
        if(payload.formatVersion!=1||payload.conversations.size>100_000||payload.memories.size>100_000)throw PersonalBackupInvalidException();return payload
    }
    private fun importTarget(owner:UUID,type:String,source:UUID)=jdbc.sql("SELECT target_id FROM personal_backup_import_record WHERE owner_id=:owner AND record_type=:type AND source_id=:source")
        .param("owner",owner).param("type",type).param("source",source).query(UUID::class.java).optional().orElse(null)
    private fun track(owner:UUID,type:String,source:UUID,target:UUID,at:Instant){jdbc.sql("INSERT INTO personal_backup_import_record(owner_id,record_type,source_id,target_id,imported_at) VALUES(:owner,:type,:source,:target,:at)")
        .param("owner",owner).param("type",type).param("source",source).param("target",target).param("at",Timestamp.from(at)).update()}
    private fun validateConversation(value:BackupConversation){if(value.title.isBlank()||value.title.length>160||value.messages.size>100_000)throw PersonalBackupInvalidException();Instant.parse(value.createdAt);Instant.parse(value.updatedAt)}
    private fun validateMessage(value:BackupMessage){if(value.role !in setOf("user","assistant")||value.content.isBlank())throw PersonalBackupInvalidException();Instant.parse(value.createdAt)}
    private fun validateMemory(value:BackupMemory){if(value.category !in setOf("preference","person","project","value","other")||value.sensitivity !in setOf("standard","sensitive")||value.status !in setOf("proposed","confirmed","superseded")||value.content.isBlank()||value.content.length>1000)throw PersonalBackupInvalidException();Instant.parse(value.createdAt);Instant.parse(value.updatedAt)}
    private fun conversations(ownerId: UUID) = jdbc.sql("SELECT id,title,created_at,updated_at FROM conversation WHERE owner_id=:ownerId ORDER BY created_at")
        .param("ownerId", ownerId).query { rs, _ ->
            val id=rs.getObject("id",UUID::class.java); BackupConversation(id,rs.getString("title"),rs.getTimestamp("created_at").toInstant().toString(),rs.getTimestamp("updated_at").toInstant().toString(),
                jdbc.sql("SELECT id,role,content,position,created_at FROM conversation_message WHERE conversation_id=:id ORDER BY position").param("id",id).query { m,_ -> BackupMessage(m.getObject("id",UUID::class.java),m.getString("role"),m.getString("content"),m.getInt("position"),m.getTimestamp("created_at").toInstant().toString()) }.list())
        }.list()
    private fun memoryEnabled(ownerId: UUID) = jdbc.sql("SELECT enabled FROM owner_memory_settings WHERE owner_id=:id").param("id",ownerId).query(Boolean::class.java).optional().orElse(false)
    private fun memories(ownerId: UUID) = jdbc.sql("SELECT id,category,content,sensitivity,status,created_at,updated_at,confirmed_at,source_conversation_id,source_message_id,conflicts_with_memory_id FROM personal_memory WHERE owner_id=:id ORDER BY created_at")
        .param("id",ownerId).query { rs,_ -> BackupMemory(rs.getObject("id",UUID::class.java),rs.getString("category"),rs.getString("content"),rs.getString("sensitivity"),rs.getString("status"),rs.getTimestamp("created_at").toInstant().toString(),rs.getTimestamp("updated_at").toInstant().toString(),rs.getTimestamp("confirmed_at")?.toInstant()?.toString(),rs.getObject("source_conversation_id",UUID::class.java),rs.getObject("source_message_id",UUID::class.java),rs.getObject("conflicts_with_memory_id",UUID::class.java)) }.list()
    private fun retention(ownerId: UUID): Map<String,String> = jdbc.sql("SELECT conversation_policy,activity_policy,personal_memory_policy FROM owner_retention_policy WHERE owner_id=:id").param("id",ownerId).query { rs,_ -> mapOf("conversations" to rs.getString(1),"activity" to rs.getString(2),"personalMemory" to rs.getString(3)) }.optional().orElse(mapOf("conversations" to "keep_forever","activity" to "keep_forever","personalMemory" to "keep_forever"))
    private fun HttpServletRequest.ownerId() = getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw UnauthenticatedException()
}

class PersonalBackupInvalidException : RuntimeException()
class PersonalBackupConfirmationException : RuntimeException()

@org.springframework.web.bind.annotation.RestControllerAdvice
class PersonalBackupErrorHandler {
    @ExceptionHandler(PersonalBackupInvalidException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid() = mapOf("code" to "BACKUP_INVALID_OR_PASSPHRASE_WRONG")
    @ExceptionHandler(PersonalBackupConfirmationException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun confirmation() = mapOf("code" to "BACKUP_IMPORT_CONFIRMATION_REQUIRED")
}

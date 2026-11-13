package dev.kyrion.core.security

import com.fasterxml.jackson.core.JsonFactory
import com.fasterxml.jackson.core.StreamReadFeature
import com.fasterxml.jackson.databind.ObjectMapper
import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityIntegrity
import dev.kyrion.core.activity.ActivityIntegrityVerifier
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.activity.JdbcActivityEventRepository
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.security.MessageDigest
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import kotlin.system.exitProcess
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.jdbc.datasource.DataSourceTransactionManager
import org.springframework.jdbc.datasource.DriverManagerDataSource
import org.springframework.transaction.support.TransactionTemplate

/** Public transfer proof plus target DB credentials; never an HTTP recovery route. */
data class OperationalTransferPermit(val source: UUID, val target: UUID, val backupSha256: String) {
    companion object {
        private val mapper = ObjectMapper(JsonFactory.builder().enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION).build())
        private val digest = Regex("[0-9a-f]{64}")

        fun verify(raw: ByteArray, key: ByteArray): OperationalTransferPermit {
            require(raw.size <= 4096 && key.size == 32)
            val root = requireNotNull(mapper.readTree(raw))
            require(root.isObject && root.fieldNames().asSequence().toSet() == setOf("transfer", "authentication"))
            val transfer = root["transfer"]
            require(transfer.isObject && transfer.fieldNames().asSequence().toSet() ==
                setOf("formatVersion", "kind", "sourceInstallationId", "targetInstallationId", "backupSha256"))
            require(transfer["formatVersion"].isIntegralNumber && transfer["formatVersion"].canConvertToInt() && transfer["formatVersion"].asInt() == 1)
            require(transfer["kind"].isTextual && transfer["kind"].asText() == "kyrion-authority-transfer")
            fun text(name: String): String {
                require(transfer[name].isTextual)
                return transfer[name].asText()
            }
            val source = UUID.fromString(text("sourceInstallationId"))
            val target = UUID.fromString(text("targetInstallationId"))
            require(source != target && source.toString() == text("sourceInstallationId") && target.toString() == text("targetInstallationId"))
            val backup = text("backupSha256")
            require(backup.matches(digest) && root["authentication"].isTextual)
            val supplied = root["authentication"].asText()
            require(supplied.matches(digest))
            val canonical = sortedMapOf<String, Any>(
                "formatVersion" to 1, "kind" to "kyrion-authority-transfer",
                "sourceInstallationId" to source.toString(), "targetInstallationId" to target.toString(),
                "backupSha256" to backup,
            )
            val mac = Mac.getInstance("HmacSHA256").apply { init(SecretKeySpec(key, "HmacSHA256")) }
            val authenticated = mac.doFinal("kyrion-operational-authority-transfer-v1\u0000".toByteArray(Charsets.US_ASCII) + mapper.writeValueAsBytes(canonical))
            require(MessageDigest.isEqual(authenticated, supplied.chunked(2).map { it.toInt(16).toByte() }.toByteArray()))
            return OperationalTransferPermit(source, target, backup)
        }
    }
}

class OperationalRestoreDisposition(
    private val jdbc: JdbcClient,
    private val transactions: TransactionTemplate,
    private val verifier: ActivityIntegrityVerifier,
    private val activity: ActivityService,
) {
    fun apply(permit: OperationalTransferPermit, recoveryDirectory: Path? = null) {
        transactions.executeWithoutResult {
            require(jdbc.sql("SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'").query(Int::class.java).single() == 49)
            val current = jdbc.sql("SELECT id FROM installation_identity WHERE singleton FOR UPDATE").query(UUID::class.java).single()
            val spaces = jdbc.sql("SELECT id FROM kyrion_space").query(UUID::class.java).list()
            require(spaces.size == 1)
            val scopes = jdbc.sql("SELECT chain_scope FROM activity_integrity_chain UNION SELECT DISTINCT chain_scope FROM activity_event WHERE chain_scope IS NOT NULL").query(String::class.java).list()
            require(scopes.all { it != null && verifier.verify(it).valid })
            if (current == permit.target) return@executeWithoutResult
            transferRecoveryHostKey(permit, requireNotNull(current), requireNotNull(spaces.single()), recoveryDirectory)
            listOf(
                "DELETE FROM auth_session",
                "DELETE FROM space_recovery_session",
                "UPDATE space_recovery_material SET code_hash=NULL,code_expires_at=CURRENT_TIMESTAMP",
                "DELETE FROM gateway_enrollment",
                "DELETE FROM voice_satellite_enrollment",
                "UPDATE gateway_node SET credential_hash=encode(sha256(convert_to(gen_random_uuid()::text||gen_random_uuid()::text,'UTF8')),'hex'),last_seen_at=NULL",
                "UPDATE voice_satellite SET credential_hash=encode(sha256(convert_to(gen_random_uuid()::text||gen_random_uuid()::text,'UTF8')),'hex')",
                "UPDATE gateway_command SET status='failed',error_code='RESTORED_COMMAND_REVOKED',completed_at=CURRENT_TIMESTAMP WHERE status IN ('pending','running','claimed')",
                "UPDATE voice_dialogue_session SET status='expired',close_reason='installation_restored',closed_at=CURRENT_TIMESTAMP WHERE status='active'",
                "UPDATE calendar_sync_schedule SET enabled=FALSE,lease_token=NULL,lease_until=NULL",
                "UPDATE household_calendar_delivery SET state='NEEDS_REVIEW',error_code='INSTALLATION_RESTORED' WHERE state='RUNNING'",
                "UPDATE home_assistant_device_selection SET control_enabled=FALSE",
            ).forEach { jdbc.sql(it).update() }
            jdbc.sql("UPDATE installation_identity SET id=:target WHERE singleton").param("target", permit.target).update()
            activity.record(
                ActivityCategory.SECURITY, "installation.restored", ActivityStatus.SUCCEEDED,
                ActivityActorType.SYSTEM, "host-maintenance", "installation.restored",
                correlationId = permit.target, ownerId = spaces.single(),
            )
        }
    }

    private fun transferRecoveryHostKey(permit: OperationalTransferPermit, originalIdentity: UUID, space: UUID, directory: Path?) {
        val existing = jdbc.sql("SELECT host_key_hash FROM space_recovery_material WHERE space_id=:space FOR UPDATE")
            .param("space", space).query(String::class.java).optional().orElse(null) ?: return
        require(directory != null && Files.isDirectory(directory, NOFOLLOW_LINKS))
        val host = ProtectedSecurityFile.read(directory.resolve("$space.host-key"))
        // Keep exactly the established LocalOwnerRecovery token namespace.
        val tokens = SessionTokenService()
        // The restored Core identity may differ from the installer's source
        // host UUID. Recovery tokens bind the locked database identity.
        val sourceHash = tokens.hash("host:$originalIdentity:$space:$host")
        require(MessageDigest.isEqual(existing.toByteArray(), sourceHash.toByteArray()))
        jdbc.sql("UPDATE space_recovery_material SET host_key_hash=:hash WHERE space_id=:space")
            .param("hash", tokens.hash("host:${permit.target}:$space:$host"))
            .param("space", space).update()
    }
}

/** Boot PropertiesLauncher entrypoint; does not create Spring HTTP/scheduler beans. */
object OperationalRestoreAdmin {
    @JvmStatic
    fun main(args: Array<String>) {
        if (args.contentEquals(arrayOf("--capability"))) {
            println("{\"formatVersion\":1,\"coreSchema\":49,\"coreOwnedDisposition\":true,\"recoveryKeyTransfer\":true}")
            return
        }
        try {
            require(args.size == 1)
            val request = Path.of(args.single()).toAbsolutePath().normalize()
            require(Files.isRegularFile(request, NOFOLLOW_LINKS) && Files.size(request) <= 4096)
            val auditPath = required("KYRION_AUDIT_INTEGRITY_KEY_FILE")
            val raw = Files.newInputStream(request, NOFOLLOW_LINKS).use { it.readNBytes(4097) }
            val key = Files.newInputStream(Path.of(auditPath), NOFOLLOW_LINKS).use { it.readNBytes(33) }
            val permit = OperationalTransferPermit.verify(raw, key)
            require(permit.target == UUID.fromString(required("KYRION_RESTORE_TARGET_ID")))
            val password = System.getenv("KYRION_DATABASE_PASSWORD_FILE")?.let {
                Files.readString(Path.of(it)).trimEnd('\r', '\n')
            } ?: required("KYRION_DATABASE_PASSWORD")
            val source = DriverManagerDataSource(required("KYRION_DATABASE_URL"), required("KYRION_DATABASE_USER"), password)
            val jdbc = JdbcClient.create(source)
            val transactions = TransactionTemplate(DataSourceTransactionManager(source))
            val integrity = ActivityIntegrity(auditPath, false)
            OperationalRestoreDisposition(jdbc, transactions, ActivityIntegrityVerifier(jdbc, integrity),
                ActivityService(JdbcActivityEventRepository(jdbc, transactions, integrity))).apply(
                    permit, System.getenv("KYRION_RESTORE_RECOVERY_DIR")?.let { Path.of(it) },
                )
        } catch (_: Exception) {
            System.err.println("E_RESTORE_SECURITY")
            exitProcess(2)
        }
    }

    private fun required(name: String) = System.getenv(name)?.takeIf { it.isNotBlank() } ?: error("Missing $name")
}

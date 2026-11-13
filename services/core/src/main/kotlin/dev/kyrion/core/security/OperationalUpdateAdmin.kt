package dev.kyrion.core.security

import dev.kyrion.core.activity.*
import java.nio.file.Files
import java.nio.file.Path
import java.util.UUID
import kotlin.system.exitProcess
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.jdbc.datasource.DataSourceTransactionManager
import org.springframework.jdbc.datasource.DriverManagerDataSource
import org.springframework.transaction.support.TransactionTemplate

/** No HTTP, scheduling, identity replacement or migration is started here. */
object OperationalUpdateAdmin {
    @JvmStatic
    fun main(args: Array<String>) {
        if (args.contentEquals(arrayOf("--capability"))) {
            println("{\"formatVersion\":1,\"updateProtocol\":1,\"sourceSchemas\":[49],\"maintenanceStart\":true}")
            return
        }
        try {
            require(args.size == 1 && args.single() in setOf("--prepare", "--completed", "--recovered", "--aborted"))
            val operation = args.single().removePrefix("--")
            val expectedSchema = required("KYRION_UPDATE_EXPECTED_SCHEMA").toInt()
            if (operation != "completed") require(expectedSchema == 49)
            val transaction = UUID.fromString(required("KYRION_UPDATE_TRANSACTION_ID"))
            val password = Files.readString(Path.of(required("KYRION_DATABASE_PASSWORD_FILE"))).trimEnd('\r', '\n')
            val source = DriverManagerDataSource(required("KYRION_DATABASE_URL"), required("KYRION_DATABASE_USER"), password)
            val jdbc = JdbcClient.create(source)
            val transactions = TransactionTemplate(DataSourceTransactionManager(source))
            val integrity = ActivityIntegrity(required("KYRION_AUDIT_INTEGRITY_KEY_FILE"), false)
            val verifier = ActivityIntegrityVerifier(jdbc, integrity)
            val activity = ActivityService(JdbcActivityEventRepository(jdbc, transactions, integrity))
            transactions.executeWithoutResult {
                require(jdbc.sql("SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'").query(Int::class.java).single() == expectedSchema)
                jdbc.sql("SELECT id FROM installation_identity WHERE singleton FOR UPDATE").query(UUID::class.java).single()
                val spaces = jdbc.sql("SELECT id FROM kyrion_space").query(UUID::class.java).list()
                require(spaces.size == 1)
                val scopes = jdbc.sql("SELECT chain_scope FROM activity_integrity_chain UNION SELECT DISTINCT chain_scope FROM activity_event WHERE chain_scope IS NOT NULL").query(String::class.java).list()
                require(scopes.all { it != null && verifier.verify(it).valid })
                val event = "installation.update." + operation.let { if (it == "prepare") "prepared" else it }
                val recorded = jdbc.sql("SELECT count(*) FROM activity_event WHERE event_type=:event AND correlation_id=:id")
                    .param("event", event).param("id", transaction).query(Long::class.java).single()
                if (recorded > 0) return@executeWithoutResult
                if (operation == "prepare") {
                    jdbc.sql("UPDATE gateway_command SET status='failed',error_code='UPDATE_EXECUTION_REVIEW_REQUIRED',completed_at=CURRENT_TIMESTAMP WHERE status IN ('running','claimed')").update()
                    jdbc.sql("UPDATE voice_dialogue_session SET status='expired',close_reason='installation_update',closed_at=CURRENT_TIMESTAMP WHERE status='active'").update()
                    jdbc.sql("UPDATE household_calendar_delivery SET state='NEEDS_REVIEW',error_code='INSTALLATION_UPDATE' WHERE state='RUNNING'").update()
                }
                if (operation == "recovered") {
                    listOf(
                        "DELETE FROM auth_session",
                        "DELETE FROM space_recovery_session",
                        "UPDATE space_recovery_material SET code_hash=NULL,code_expires_at=CURRENT_TIMESTAMP",
                        "DELETE FROM gateway_enrollment", "DELETE FROM voice_satellite_enrollment",
                        "UPDATE gateway_node SET credential_hash=encode(sha256(convert_to(gen_random_uuid()::text||gen_random_uuid()::text,'UTF8')),'hex'),last_seen_at=NULL",
                        "UPDATE voice_satellite SET credential_hash=encode(sha256(convert_to(gen_random_uuid()::text||gen_random_uuid()::text,'UTF8')),'hex')",
                        "UPDATE gateway_command SET status='failed',error_code='UPDATE_RECOVERY_REVIEW_REQUIRED',completed_at=CURRENT_TIMESTAMP WHERE status IN ('pending','running','claimed')",
                        "UPDATE voice_dialogue_session SET status='expired',close_reason='update_recovery',closed_at=CURRENT_TIMESTAMP WHERE status='active'",
                        "UPDATE calendar_sync_schedule SET enabled=FALSE,lease_token=NULL,lease_until=NULL",
                        "UPDATE household_calendar_delivery SET state='NEEDS_REVIEW',error_code='UPDATE_RECOVERY' WHERE state='RUNNING'",
                        "UPDATE home_assistant_device_selection SET control_enabled=FALSE",
                    ).forEach { jdbc.sql(it).update() }
                }
                activity.record(
                    ActivityCategory.SECURITY, event, ActivityStatus.SUCCEEDED,
                    ActivityActorType.SYSTEM, "host-maintenance", event,
                    correlationId = transaction, ownerId = spaces.single(),
                )
            }
        } catch (_: Exception) {
            System.err.println("E_UPDATE_SECURITY")
            exitProcess(2)
        }
    }

    private fun required(name: String) = System.getenv(name)?.takeIf { it.isNotBlank() } ?: error("Missing $name")
}

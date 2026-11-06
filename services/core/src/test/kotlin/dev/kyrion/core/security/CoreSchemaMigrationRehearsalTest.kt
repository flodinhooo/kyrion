package dev.kyrion.core.security

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import org.assertj.core.api.Assertions.assertThat
import org.flywaydb.core.Flyway
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.postgresql.PostgreSQLContainer
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import java.sql.DriverManager
import java.time.Duration
import java.util.UUID
import java.util.concurrent.TimeUnit

/** Actual operator tool + actual pinned bootJar, disposable databases only, no Spring. */
@Testcontainers
class CoreSchemaMigrationRehearsalTest {
    @TempDir lateinit var directory: Path
    private val json = ObjectMapper()
    private val root = Path.of("../..").toAbsolutePath().normalize()
    private val artifact get() = Path.of(requireNotNull(System.getenv("KYRION_MIGRATION_REHEARSAL_JAR")) {
        "Run infrastructure/dev/Test-CoreSchemaMigration.ps1; an immutable built artifact is mandatory"
    })
    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    private fun database(): String = "schema_" + UUID.randomUUID().toString().replace("-", "")
    private fun command(vararg args: String) {
        val result = postgres.execInContainer(*args)
        assertThat(result.exitCode).withFailMessage("Synthetic PostgreSQL command failed: %s", result.stderr).isZero()
    }
    private fun url(database: String) = "jdbc:postgresql://${postgres.host}:${postgres.getMappedPort(5432)}/$database"
    private fun sql(database: String, text: String) {
        DriverManager.getConnection(url(database), postgres.username, postgres.password).use { it.createStatement().use { statement -> statement.execute(text) } }
    }
    private fun value(database: String, text: String): String =
        DriverManager.getConnection(url(database), postgres.username, postgres.password).use { db -> db.createStatement().use { statement ->
            statement.executeQuery(text).use { rows -> check(rows.next()); rows.getString(1) }
        } }
    private fun create(version: Int): String {
        val database = database()
        command("createdb", "-U", postgres.username, database)
        Flyway.configure().dataSource(url(database), postgres.username, postgres.password).target(version.toString()).load().migrate()
        return database
    }
    private fun restore(source: String): String {
        val target = database()
        val dump = "/tmp/$target.dump"
        command("pg_dump", "-U", postgres.username, "-Fc", "--no-owner", "--no-acl", "-f", dump, source)
        command("createdb", "-U", postgres.username, target)
        command("pg_restore", "-U", postgres.username, "--exit-on-error", "--no-owner", "--no-acl", "-d", target, dump)
        return target
    }
    private fun connection(database: String): Path {
        val file = directory.resolve("$database.json")
        Files.writeString(file, json.writeValueAsString(mapOf("host" to "127.0.0.1", "port" to postgres.getMappedPort(5432), "database" to database,
            "user" to postgres.username, "password" to postgres.password, "sslmode" to "disable")))
        return file
    }
    private fun tool(database: String, plan: Path, apply: Boolean = false, success: Boolean = true, target: String? = null, version: Int = 46, timeZone: String? = null): JsonNode {
        val args = mutableListOf(System.getenv("KYRION_MIGRATION_PYTHON") ?: "python", root.resolve("infrastructure/dev/Migrate-CoreSchema.py").toString(),
            "--artifact", artifact.toString(), "--artifact-sha256", hash(Files.readAllBytes(artifact)),
            "--target-version", version.toString(), "--connection-file", connection(database).toString(), "--plan", plan.toString(), "--java-home", System.getProperty("java.home"))
        if (apply) args.addAll(listOf("--apply", "--approve-plan-sha256", hash(Files.readAllBytes(plan)),
            "--expected-target", target ?: json.readTree(Files.readString(plan))["state"]["targetIdentity"].asText()))
        val output = directory.resolve("tool-${UUID.randomUUID()}.json")
        val builder = ProcessBuilder(args).redirectErrorStream(true).redirectOutput(output.toFile())
        if (timeZone != null) builder.environment()["JAVA_TOOL_OPTIONS"] = "-Duser.timezone=$timeZone"
        val process = builder.start()
        assertThat(process.waitFor(180, TimeUnit.SECONDS)).isTrue()
        val content = Files.readString(output)
        assertThat(process.exitValue()).withFailMessage("Schema-only tool result: %s", content).isEqualTo(if (success) 0 else 1)
        return json.readTree(content)
    }
    private fun snapshot(database: String, table: String) = value(database,
        "SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb)::text FROM $table t")

    private fun rehearse(version: Int) {
        val source = create(version)
        val owner = UUID.randomUUID()
        val member = UUID.randomUUID()
        val role = UUID.randomUUID()
        val google = UUID.randomUUID()
        val node = UUID.randomUUID()
        val button = UUID.randomUUID()
        val device = UUID.randomUUID()
        val commandId = UUID.randomUUID()
        sql(source, """
            INSERT INTO user_account(id,username,password_hash) VALUES('$owner','synthetic-owner','synthetic-hash');
            INSERT INTO user_account(id,username,password_hash,workspace_owner_id,enabled) VALUES('$member','synthetic-member','synthetic-hash','$owner',false);
            INSERT INTO rbac_role(id,installation_owner_id,role_key,display_name) VALUES('$role','$owner','SYNTHETIC','Synthetic');
            INSERT INTO rbac_role_permission(role_id,permission_key) VALUES('$role','devices:read');
            INSERT INTO rbac_user_role(user_id,role_id) VALUES('$member','$role');
            INSERT INTO auth_session(id,user_id,token_hash,expires_at,revoked_at) VALUES('${UUID.randomUUID()}','$member',repeat('b',64),CURRENT_TIMESTAMP+INTERVAL '1 day',CURRENT_TIMESTAMP);
            INSERT INTO activity_event(id,owner_id,occurred_at,category,event_type,status,actor_type,actor_id,source,correlation_id,summary_code,
                integrity_version,chain_scope,event_hash,previous_hash)
                VALUES('${UUID.randomUUID()}','$owner',CURRENT_TIMESTAMP,'SECURITY','synthetic','DENIED','USER','$member','synthetic','${UUID.randomUUID()}','synthetic',1,'synthetic',decode('010203','hex'),decode('040506','hex'));
            INSERT INTO activity_integrity_chain(chain_scope,last_hash,anchor_mac,updated_at) VALUES('synthetic',decode('010203','hex'),decode('040506','hex'),CURRENT_TIMESTAMP);
            INSERT INTO gateway_node(id,owner_id,display_name,hostname,credential_hash,agent_version,os_name,os_version,architecture,created_at,updated_at)
                VALUES('$node','$owner','Synthetic','synthetic',repeat('a',64),'test','test','test','test',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);
        """.trimIndent())
        for ((id, provider, address) in listOf(Triple(google, "google", "calendar.invalid"), Triple(button, "zigbee", "0x0011223344556688"), Triple(device, "zigbee", "0x0011223344556677"))) {
            sql(source, """INSERT INTO integration_connection(id,owner_id,provider,display_name,endpoint_host,credential_ciphertext,credential_nonce,created_at,updated_at)
                VALUES('$id','$owner','$provider','Synthetic','$address',decode('010203','hex'),decode('040506','hex'),CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
        }
        sql(source, """
            INSERT INTO zigbee_button_binding(owner_id,button_connection_id,gesture,target_connection_id,action,updated_at)
                VALUES('$owner','$button','single','$device','turn_on',CURRENT_TIMESTAMP);
            INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at,correlation_id)
                VALUES('$commandId','$node','$owner','zigbee.power','[]','pending',CURRENT_TIMESTAMP,'$commandId');
        """.trimIndent())
        if (version >= 43) {
            sql(source, """UPDATE gateway_command SET authority='{"spaceId":"$owner","kind":"HUMAN","principalId":"$member","permission":"devices:execute","capability":"power.set"}' WHERE id='$commandId';
                INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at,correlation_id)
                VALUES('${UUID.randomUUID()}','$node','$owner','zigbee.power','[]','pending',CURRENT_TIMESTAMP,'${UUID.randomUUID()}');""")
            // Retain an explicitly attributed but currently revoked (disabled actor) grant.
            // Migration must neither refresh it nor infer approval for the legacy single binding.
            sql(source, """INSERT INTO zigbee_button_binding(owner_id,button_connection_id,gesture,target_connection_id,action,updated_at,grant_id,granted_by,source_node_id)
                VALUES('$owner','$button','double','$device','turn_off',CURRENT_TIMESTAMP,'${UUID.randomUUID()}','$member','$node')""")
        }
        if (version == 39) sql(source, """INSERT INTO ai_usage_attempt(id,actor_id,request_id,attempt,provider,profile_id,model_id,period,charged_tokens,estimated_cost,state)
            VALUES('${UUID.randomUUID()}','$owner','${UUID.randomUUID()}',0,'synthetic','synthetic','synthetic','2026-11',17,0.25,'pending')""")
        if (version == 44) sql(source, """INSERT INTO personal_calendar_disclosure(id,space_id,user_id,connection_id,calendar_id,visibility,revision)
            VALUES('${UUID.randomUUID()}','$owner','$owner','$google','synthetic-calendar','PRIVATE',3)""")
        val immutable = listOf("user_account", "kyrion_space", "rbac_role", "rbac_permission", "rbac_user_role", "rbac_role_permission", "auth_session", "integration_connection", "activity_event", "activity_integrity_chain")
        val before = immutable.associateWith { snapshot(source, it) }
        val history = snapshot(source, "flyway_schema_history")
        val candidate = restore(source)
        val rollback = restore(source)
        val plan = directory.resolve("plan-$version.json")
        tool(candidate, plan)
        assertThat(snapshot(candidate, "flyway_schema_history")).isEqualTo(history) // planning did not migrate
        val planState = json.readTree(Files.readString(plan))["state"]
        assertThat(planState["version"].asInt()).isEqualTo(version)
        assertThat(tool(candidate, plan, apply = true)["migrationsExecuted"].asInt()).isEqualTo(46-version)
        for ((table, data) in before) assertThat(snapshot(candidate, table)).describedAs(table).isEqualTo(data)
        assertThat(value(candidate, "SELECT count(*) FROM flyway_schema_history WHERE success")).isEqualTo("46")
        assertThat(value(candidate, "SELECT count(*) FROM household_calendar_destination")).isEqualTo("0")
        assertThat(value(candidate, "SELECT count(*) FROM household_calendar_delivery")).isEqualTo("0")
        assertThat(value(candidate, "SELECT count(*) FROM personal_calendar_disclosure WHERE visibility<>'PRIVATE'")).isEqualTo("0")
        assertThat(value(candidate, "SELECT count(*) FROM personal_calendar_disclosure")).isEqualTo(if (version == 44) "1" else "0")
        assertThat(value(candidate, "SELECT count(*) FROM zigbee_button_binding WHERE gesture='single' AND grant_id IS NULL AND granted_by IS NULL AND source_node_id IS NULL")).isEqualTo("1")
        if (version >= 43) assertThat(snapshot(candidate, "zigbee_button_binding")).isEqualTo(snapshot(source, "zigbee_button_binding"))
        assertThat(value(candidate, "SELECT count(*) FROM gateway_command WHERE authority IS NULL AND status='pending' AND payload='[]'::jsonb")).isEqualTo("1")
        if (version >= 43) assertThat(snapshot(candidate, "gateway_command")).isEqualTo(snapshot(source, "gateway_command"))
        if (version == 39) assertThat(value(candidate, "SELECT state='uncertain' AND error_code='LEGACY_REVIEW_REQUIRED' AND reserved_tokens=17 AND reserved_cost=0.25 FROM ai_usage_attempt")).isEqualTo("t")
        // Real history is extended, never reconstructed: every original complete row is unchanged.
        assertThat(value(candidate, "SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb)::text FROM flyway_schema_history t WHERE version::int<=$version")).isEqualTo(history)
        for (database in listOf(source, rollback)) {
            assertThat(snapshot(database, "flyway_schema_history")).isEqualTo(history)
            for ((table, data) in before) assertThat(snapshot(database, table)).isEqualTo(data)
        }
        // Explicitly stale the plan through an authorization change; no migration or dispatch follows.
        val stale = directory.resolve("stale-$version.json")
        tool(candidate, stale)
        sql(candidate, "UPDATE user_account SET enabled=true WHERE id='$member'")
        assertThat(tool(candidate, stale, apply = true, success = false)["code"].asText()).isEqualTo("PLAN_SOURCE_DRIFT")
        assertThat(tool(rollback, plan, apply = true, success = false)["code"].asText()).isEqualTo("TARGET_IDENTITY_MISMATCH")
    }

    @Test fun `V39 restore migrates only schema through V46`() = rehearse(39)
    @Test fun `V41 restore migrates only schema through V46`() = rehearse(41)
    @Test fun `V43 restore migrates only schema through V46`() = rehearse(43)
    @Test fun `V44 restore migrates only schema through V46`() = rehearse(44)

    @Test fun `plans normalize timestamps across JVM timezones`() {
        val source = create(45)
        sql(source, "INSERT INTO user_account(id,username,password_hash) VALUES('${UUID.randomUUID()}','timezone-fixture','synthetic-hash')")
        val utc = directory.resolve("timezone-utc.json")
        val zurich = directory.resolve("timezone-zurich.json")
        tool(source, utc, timeZone = "UTC")
        tool(source, zurich, timeZone = "Europe/Zurich")
        assertThat(json.readTree(Files.readString(utc))["state"])
            .isEqualTo(json.readTree(Files.readString(zurich))["state"])
    }

    @Test fun `V45 independent restore retains disclosures grants and every delivery state without resume`() {
        val source = create(45)
        val owner = UUID.randomUUID()
        val google = UUID.randomUUID()
        val grant = UUID.randomUUID()
        val revoked = UUID.randomUUID()
        val event = UUID.randomUUID()
        sql(source, """
            INSERT INTO user_account(id,username,password_hash) VALUES('$owner','synthetic-owner','synthetic-hash');
            INSERT INTO integration_connection(id,owner_id,provider,display_name,endpoint_host,credential_ciphertext,credential_nonce,created_at,updated_at)
                VALUES('$google','$owner','google','Synthetic','calendar.invalid',decode('010203','hex'),decode('040506','hex'),CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);
            INSERT INTO personal_calendar_disclosure(id,space_id,user_id,connection_id,calendar_id,visibility,revision)
                VALUES('${UUID.randomUUID()}','$owner','$owner','$google','synthetic-calendar','DETAILS',4),
                ('${UUID.randomUUID()}','$owner','$owner','$google','synthetic-busy','AVAILABILITY',2),
                ('${UUID.randomUUID()}','$owner','$owner','$google','synthetic-private','PRIVATE',3);
            INSERT INTO household_calendar_destination(id,space_id,user_id,connection_id,calendar_id,active,revision)
                VALUES('$grant','$owner','$owner','$google','synthetic-calendar',true,2),('$revoked','$owner','$owner',NULL,'old-calendar',false,1);
            INSERT INTO household_calendar_event(id,space_id,created_by,title,starts_at,ends_at,time_zone,revision)
                VALUES('$event','$owner','$owner','Synthetic',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP+INTERVAL '1 hour','UTC',3);
            INSERT INTO household_calendar_participant(event_id,space_id,user_id) VALUES('$event','$owner','$owner');
        """.trimIndent())
        for ((index, state) in listOf("RUNNING", "SYNCED", "ERROR", "CONFLICT", "BLOCKED", "NEEDS_REVIEW").withIndex()) {
            sql(source, """INSERT INTO household_calendar_delivery(id,space_id,event_id,target_user_id,grant_id,destination_key,remote_id,etag,delivered_revision,write_started,state,error_code,attempt_id,lease_until)
                VALUES('${UUID.randomUUID()}','$owner','$event','$owner','$grant','synthetic-$index','remote-$index','synthetic-etag',2,true,'$state','SYNTHETIC','${UUID.randomUUID()}',CURRENT_TIMESTAMP+INTERVAL '${if (index == 0) "5 minutes" else "-1 hour"}')""")
        }
        val v45Plan = directory.resolve("v45-compatibility.json")
        tool(source, v45Plan, version = 45)
        assertThat(tool(source, v45Plan, apply = true, version = 45)["migrationsExecuted"].asInt()).isZero()
        val plan = directory.resolve("v45-source.json")
        tool(source, plan)
        val restored = restore(source)
        val restoredPlan = directory.resolve("v45-restored.json")
        tool(restored, restoredPlan)
        val original = json.readTree(Files.readString(plan))["state"]
        val copy = json.readTree(Files.readString(restoredPlan))["state"]
        assertThat(copy["targetIdentity"]).isNotEqualTo(original["targetIdentity"])
        assertThat(copy["tables"]).isEqualTo(original["tables"])
        assertThat(tool(restored, plan, apply = true, success = false)["code"].asText()).isEqualTo("TARGET_IDENTITY_MISMATCH")
        assertThat(tool(restored, restoredPlan, apply = true)["migrationsExecuted"].asInt()).isEqualTo(1) // no application or lease consumer
        assertThat(snapshot(restored, "household_calendar_delivery")).isEqualTo(snapshot(source, "household_calendar_delivery"))
        assertThat(snapshot(restored, "household_calendar_destination")).isEqualTo(snapshot(source, "household_calendar_destination"))
        assertThat(snapshot(restored, "personal_calendar_disclosure")).isEqualTo(snapshot(source, "personal_calendar_disclosure"))
    }

    @Test fun `invalid checksum failed history live session and missing schema are rejected`() {
        val source = create(44)
        val plan = directory.resolve("invalid.json")
        tool(source, plan)
        DriverManager.getConnection(url(source), postgres.username, postgres.password).use {
            assertThat(tool(source, plan, apply = true, success = false)["code"].asText()).isEqualTo("TARGET_NOT_QUIESCENT")
        }
        sql(source, "UPDATE flyway_schema_history SET checksum=checksum+1 WHERE version='1'")
        assertThat(tool(source, directory.resolve("checksum.json"), success = false)["code"].asText()).isEqualTo("FLYWAY_OR_DATABASE_REJECTED")
        sql(source, "UPDATE flyway_schema_history SET success=false WHERE version='1'")
        assertThat(tool(source, directory.resolve("failed.json"), success = false)["code"].asText()).isEqualTo("SOURCE_HISTORY_INVALID")
        val empty = database()
        command("createdb", "-U", postgres.username, empty)
        assertThat(tool(empty, directory.resolve("empty.json"), success = false)["code"].asText()).isEqualTo("FLYWAY_OR_DATABASE_REJECTED")
        assertThat(value(empty, "SELECT count(*) FROM pg_tables WHERE schemaname='public'")).isEqualTo("0")
    }

    companion object {
        @Container @JvmStatic val postgres = PostgreSQLContainer("postgres:17-alpine").withTmpFs(mapOf("/var/lib/postgresql/data" to "rw")).withStartupTimeout(Duration.ofMinutes(2))
    }
}

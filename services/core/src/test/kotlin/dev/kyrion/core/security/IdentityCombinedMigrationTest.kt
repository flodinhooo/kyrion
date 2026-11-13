package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.flywaydb.core.Flyway
import org.junit.jupiter.api.Test
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.postgresql.PostgreSQLContainer
import java.sql.DriverManager
import java.util.UUID
import java.nio.file.Files
import java.nio.file.Path
import org.junit.jupiter.api.io.TempDir

@Testcontainers
class IdentityCombinedMigrationTest {
    @TempDir lateinit var temporary: Path
    private fun migrate(schema: String, target: String? = null) = Flyway.configure()
        .dataSource(postgres.jdbcUrl, postgres.username, postgres.password)
        .schemas(schema).defaultSchema(schema).locations("classpath:db/migration")
        .apply { if (target != null) target(target) }.load()

    @Test fun `fresh database has unique ordered canonical migrations and repeated startup is a no-op`() {
        val schema = "fresh_" + UUID.randomUUID().toString().replace("-", "")
        val flyway = migrate(schema)
        assertThat(flyway.migrate().migrationsExecuted).isEqualTo(49)
        flyway.validate()
        assertThat(flyway.info().applied().filter { it.version != null }.map { it.version.version }).containsExactlyElementsOf((1..49).map(Int::toString))
        assertThat(flyway.migrate().migrationsExecuted).isZero()
    }

    @Test fun `V41 through canonical calendar V44 to identity V46 preserves credentials calendars and gateway authority`() {
        val schema = "upgrade_" + UUID.randomUUID().toString().replace("-", "")
        migrate(schema, "41").migrate()
        val owner = UUID.randomUUID()
        val member = UUID.randomUUID()
        val node = UUID.randomUUID()
        val command = UUID.randomUUID()
        val event = UUID.randomUUID()
        val google = UUID.randomUUID()
        DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password).use { connection ->
            connection.schema = schema
            connection.createStatement().use { sql ->
                sql.execute("INSERT INTO user_account(id,username,password_hash) VALUES('$owner','existing-owner','preserved-owner-hash')")
                sql.execute("INSERT INTO user_account(id,username,password_hash,workspace_owner_id) VALUES('$member','existing-member','preserved-member-hash','$owner')")
                sql.execute("UPDATE installation_bootstrap_state SET initialized=TRUE")
                sql.execute("INSERT INTO rbac_role(id,installation_owner_id,role_key,display_name,system_role) VALUES('$owner','$owner','OWNER','Owner',TRUE),('$member','$owner','USER','Member',TRUE)")
                sql.execute("INSERT INTO rbac_user_role(user_id,role_id) VALUES('$owner','$owner'),('$member','$member')")
                sql.execute("INSERT INTO rbac_role_permission(role_id,permission_key) VALUES('$member','calendar:read')")
                sql.execute("INSERT INTO auth_session(id,user_id,token_hash,expires_at) VALUES(gen_random_uuid(),'$member',repeat('c',64),CURRENT_TIMESTAMP+INTERVAL '1 day')")
                sql.execute("INSERT INTO integration_connection(id,owner_id,provider,display_name,endpoint_host,credential_ciphertext,credential_nonce,created_at,updated_at) VALUES(gen_random_uuid(),'$owner','home_assistant','fixture','127.0.0.1',decode('010203','hex'),decode('0405','hex'),now(),now())")
                sql.execute("INSERT INTO local_calendar_event(id,owner_id,title,starts_at,ends_at,time_zone,content_fingerprint,created_at,updated_at) VALUES(gen_random_uuid(),'$owner','legacy event',now(),now()+INTERVAL '1 hour','Europe/Zurich','fixture',now(),now())")
                sql.execute("INSERT INTO gateway_node(id,owner_id,display_name,hostname,credential_hash,agent_version,os_name,os_version,architecture,created_at,updated_at) VALUES('$node','$owner','synthetic','synthetic.invalid',repeat('d',64),'fixture','fixture','fixture','fixture',now(),now())")
                sql.execute("INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at) VALUES('$command','$node','$owner','fixture','{}','pending',now())")
                migrate(schema, "42").migrate()
                sql.executeQuery("SELECT authority IS NULL FROM gateway_command WHERE id='$command'").use { it.next(); assertThat(it.getBoolean(1)).isTrue() }
                // Synthetic provenance marker: migration must preserve it, never interpret/grant it.
                sql.execute("UPDATE gateway_command SET authority='{\"fixture\":\"preserve-explicit-provenance\"}' WHERE id='$command'")
                migrate(schema, "43").migrate()
                sql.execute("INSERT INTO household_calendar_event(id,space_id,created_by,title,starts_at,ends_at,time_zone) VALUES('$event','$owner','$owner','household event',now(),now()+INTERVAL '1 hour','Europe/Zurich')")
                sql.execute("INSERT INTO household_calendar_participant(event_id,space_id,user_id) VALUES('$event','$owner','$owner'),('$event','$owner','$member')")
                migrate(schema, "44").migrate()
                sql.execute("INSERT INTO integration_connection(id,owner_id,provider,display_name,endpoint_host,credential_ciphertext,credential_nonce,created_at,updated_at) VALUES('$google','$owner','google','fixture','google-fixture',decode('010203','hex'),decode('0405','hex'),now(),now())")
                sql.execute("INSERT INTO personal_calendar_disclosure(id,space_id,user_id,connection_id,calendar_id,visibility,revision) VALUES(gen_random_uuid(),'$owner','$owner','$google','synthetic-calendar','AVAILABILITY',1)")
                migrate(schema, "45").migrate()
                val destination = UUID.randomUUID()
                sql.execute("INSERT INTO household_calendar_destination(id,space_id,user_id,connection_id,calendar_id,active,revision) VALUES('$destination','$owner','$owner','$google','synthetic-calendar',TRUE,1)")
                sql.execute("INSERT INTO household_calendar_delivery(id,space_id,event_id,target_user_id,grant_id,destination_key,remote_id,etag,delivered_revision,state,attempt_id,lease_until) VALUES(gen_random_uuid(),'$owner','$event','$owner','$destination','synthetic-key','synthetic-remote','synthetic-etag',0,'SYNCED',gen_random_uuid(),now())")
                val before = linkedMapOf<String, String>()
                val tables = listOf("user_account", "kyrion_space", "rbac_role", "rbac_user_role", "rbac_role_permission", "auth_session", "integration_connection", "local_calendar_event", "gateway_node", "gateway_command", "household_calendar_event", "household_calendar_participant", "personal_calendar_disclosure", "household_calendar_destination", "household_calendar_delivery", "installation_bootstrap_state")
                fun snapshot(table: String): String = sql.executeQuery("SELECT COALESCE(jsonb_agg(row ORDER BY row::text),'[]'::jsonb)::text FROM (SELECT to_jsonb(t) AS row FROM $table t) rows").use { it.next(); it.getString(1) }
                tables.forEach { before[it] = snapshot(it) }
                val checksums = migrate(schema).info().applied().filter { it.version != null }.associate { it.version.version to it.checksum }
                // This historical acceptance isolates V46; later canonical
                // migrations have their own schema/data transformation tests.
                assertThat(migrate(schema, "46").migrate().migrationsExecuted).isEqualTo(1)
                migrate(schema, "46").validate()
                assertThat(migrate(schema, "46").migrate().migrationsExecuted).isZero()
                tables.forEach { assertThat(snapshot(it)).describedAs("preserved %s", it).isEqualTo(before[it]) }
                assertThat(migrate(schema, "46").info().applied().filter { it.version != null && it.version.version != "46" }.associate { it.version.version to it.checksum }).isEqualTo(checksums)
                sql.executeQuery("SELECT count(*) FROM central_identity_link").use { it.next(); assertThat(it.getInt(1)).isZero() }
            }
        }
    }

    @Test fun `former identity V44 history stops before canonical migration without repair or data changes`() {
        val schema = "divergent_" + UUID.randomUUID().toString().replace("-", "")
        Files.newDirectoryStream(Path.of("src/main/resources/db/migration")).use { files ->
            files.filter { Regex("V(\\d+)__.*").matchEntire(it.fileName.toString())?.groupValues?.get(1)?.toInt()?.let { version -> version <= 41 } == true }
                .forEach { Files.copy(it, temporary.resolve(it.fileName)) }
        }
        javaClass.getResourceAsStream("/identity-legacy/V44__optional_central_identity.sql")!!.use {
            Files.copy(it, temporary.resolve("V44__optional_central_identity.sql"))
        }
        Flyway.configure().dataSource(postgres.jdbcUrl, postgres.username, postgres.password)
            .schemas(schema).defaultSchema(schema).locations("filesystem:$temporary").load().migrate()
        DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password).use { connection ->
            connection.schema = schema
            connection.createStatement().use { statement ->
                val owner = UUID.randomUUID()
                statement.execute("INSERT INTO user_account(id,username,password_hash) VALUES('$owner','legacy-owner','preserved-legacy-hash')")
                statement.execute("INSERT INTO central_identity_link(user_id,issuer,subject,linked_at) VALUES('$owner','https://synthetic.invalid','preserved-subject',now())")
                assertThatThrownBy { migrate(schema).migrate() }.isInstanceOf(org.flywaydb.core.api.exception.FlywayValidateException::class.java)
                statement.executeQuery("SELECT count(*) FROM flyway_schema_history WHERE version='46'").use { it.next(); assertThat(it.getInt(1)).isZero() }
                statement.executeQuery("SELECT subject FROM central_identity_link WHERE user_id='$owner'").use { it.next(); assertThat(it.getString(1)).isEqualTo("preserved-subject") }
                statement.executeQuery("SELECT password_hash FROM user_account WHERE id='$owner'").use { it.next(); assertThat(it.getString(1)).isEqualTo("preserved-legacy-hash") }
                statement.executeQuery("SELECT count(*) FROM information_schema.tables WHERE table_schema='$schema' AND table_name='personal_calendar_disclosure'").use { it.next(); assertThat(it.getInt(1)).isZero() }
            }
        }
    }

    companion object {
        @Container @JvmStatic val postgres = PostgreSQLContainer("postgres:17-alpine").withTmpFs(mapOf("/var/lib/postgresql/data" to "rw"))
            .withEnv("POSTGRES_INITDB_ARGS", "--no-sync").withStartupTimeout(java.time.Duration.ofMinutes(3))
    }
}
